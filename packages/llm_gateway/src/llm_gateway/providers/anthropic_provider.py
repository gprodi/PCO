"""Fournisseur Claude via le SDK officiel ``anthropic`` (extra optionnel : ``llm-gateway[anthropic]``).

Dernier maillon de la chaîne (payant à l'usage). Choix appliqués :

* modèle par défaut ``claude-opus-5-5`` (configurable dans profiles.yaml) ;
* ``output_config.effort`` explicite (défaut ``medium`` sur ce modèle) ;
* sorties structurées via ``output_config.format`` (JSON Schema strict) ;
* **fallback serveur activé** (``fallbacks="default"``) : si le modèle refuse pour raison de
  sécurité, l'API rejoue la requête sur un modèle de repli ; si toute la chaîne refuse
  (``stop_reason == "refusal"``), on lève ProviderUnavailableError pour passer au suivant.
"""

from __future__ import annotations

import base64
import time
from typing import Any

from llm_gateway.errors import ProviderUnavailableError
from llm_gateway.providers.base import Provider
from llm_gateway.schema_utils import strict_schema
from llm_gateway.types import ChatRequest, ChatResult

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider(Provider):
    """Claude (Messages API) — texte, vision, JSON ; pas d'embeddings."""

    name = "anthropic"
    supports_embeddings = False

    def __init__(
        self,
        api_key: str | None,
        effort: str = "medium",
        timeout_s: float = 120.0,
        client: Any | None = None,
    ) -> None:
        self.api_key = api_key
        self.effort = effort
        self.timeout_s = timeout_s
        self._client = client

    def is_configured(self) -> bool:
        if self._client is not None:
            return True
        if not self.api_key:
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout_s)
        return self._client

    @staticmethod
    def _content(request: ChatRequest) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        for img in request.images:
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img.media_type,
                        "data": base64.standard_b64encode(img.data).decode("utf-8"),
                    },
                }
            )
        blocks.append({"type": "text", "text": request.prompt})
        return blocks

    def chat(self, request: ChatRequest, model: str) -> ChatResult:
        client = self._get_client()
        output_config: dict[str, Any] = {"effort": self.effort}
        if request.json_schema is not None:
            output_config["format"] = {
                "type": "json_schema",
                "schema": strict_schema(request.json_schema),
            }
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max(request.max_tokens, 16000),
            "messages": [{"role": "user", "content": self._content(request)}],
            "output_config": output_config,
            "betas": [FALLBACK_BETA],
            "fallbacks": "default",
        }
        if request.system:
            kwargs["system"] = request.system

        start = time.perf_counter()
        try:
            response = client.beta.messages.create(**kwargs)
        except Exception as exc:  # erreurs réseau / quota / auth du SDK
            raise ProviderUnavailableError(f"anthropic : {exc}") from exc
        latency = time.perf_counter() - start

        if getattr(response, "stop_reason", None) == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise ProviderUnavailableError(f"anthropic : refus (catégorie {category})")

        text = "".join(
            getattr(block, "text", "")
            for block in response.content
            if getattr(block, "type", None) == "text"
        )
        usage = getattr(response, "usage", None)
        return ChatResult(
            text=text,
            provider=self.name,
            model=getattr(response, "model", model),
            latency_s=latency,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )
