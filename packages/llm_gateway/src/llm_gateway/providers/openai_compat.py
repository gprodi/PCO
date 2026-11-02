"""Fournisseur générique pour les API compatibles OpenAI : Ollama (/v1), Gemini, LiteLLM.

On utilise httpx directement : une seule dépendance légère pour trois back-ends.
"""

from __future__ import annotations

import base64
import time
from typing import Any

import httpx
from loguru import logger

from llm_gateway.errors import ProviderUnavailableError
from llm_gateway.providers.base import Provider
from llm_gateway.schema_utils import strict_schema
from llm_gateway.types import ChatRequest, ChatResult


class OpenAICompatProvider(Provider):
    """Chat completions + embeddings sur une API compatible OpenAI."""

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str | None = None,
        timeout_s: float = 120.0,
        requires_key: bool = False,
        client: httpx.Client | None = None,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.requires_key = requires_key
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = client or httpx.Client(timeout=timeout_s, headers=headers)

    def is_configured(self) -> bool:
        return bool(self.api_key) or not self.requires_key

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _content(request: ChatRequest) -> str | list[dict[str, Any]]:
        if not request.images:
            return request.prompt
        parts: list[dict[str, Any]] = [{"type": "text", "text": request.prompt}]
        for img in request.images:
            b64 = base64.b64encode(img.data).decode("ascii")
            parts.append(
                {"type": "image_url", "image_url": {"url": f"data:{img.media_type};base64,{b64}"}}
            )
        return parts

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            resp = self._client.post(url, json=payload)
        except httpx.HTTPError as exc:  # connexion refusée, timeout…
            raise ProviderUnavailableError(f"{self.name} injoignable : {exc}") from exc
        if resp.status_code in (401, 403, 404, 408, 429) or resp.status_code >= 500:
            raise ProviderUnavailableError(
                f"{self.name} HTTP {resp.status_code} : {resp.text[:300]}"
            )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------ API
    def chat(self, request: ChatRequest, model: str) -> ChatResult:
        messages: list[dict[str, Any]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": self._content(request)})
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.json_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "schema": strict_schema(request.json_schema),
                    "strict": True,
                },
            }
        start = time.perf_counter()
        data = self._post("/chat/completions", payload)
        latency = time.perf_counter() - start
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderUnavailableError(
                f"{self.name} : réponse inattendue {data!r:.300}"
            ) from exc
        usage = data.get("usage") or {}
        logger.debug("{} {} en {:.2f}s", self.name, model, latency)
        return ChatResult(
            text=text,
            provider=self.name,
            model=model,
            latency_s=latency,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        data = self._post("/embeddings", {"model": model, "input": texts})
        rows = sorted(data["data"], key=lambda r: r.get("index", 0))
        return [row["embedding"] for row in rows]


def ollama_provider(base_url: str, timeout_s: float = 120.0) -> OpenAICompatProvider:
    """Ollama expose une API compatible OpenAI sous /v1."""
    return OpenAICompatProvider("ollama", f"{base_url.rstrip('/')}/v1", timeout_s=timeout_s)


def gemini_provider(
    api_key: str | None, base_url: str, timeout_s: float = 120.0
) -> OpenAICompatProvider:
    """Gemini via son endpoint compatible OpenAI (offre gratuite, quotas variables)."""
    return OpenAICompatProvider(
        "gemini", base_url, api_key=api_key, timeout_s=timeout_s, requires_key=True
    )


def litellm_provider(
    base_url: str | None, api_key: str | None, timeout_s: float = 120.0
) -> OpenAICompatProvider:
    """Passerelle LiteLLM (clés virtuelles, quotas, fallbacks gérés côté proxy)."""
    provider = OpenAICompatProvider(
        "litellm", (base_url or "").rstrip("/") + "/v1", api_key=api_key, timeout_s=timeout_s
    )
    provider.requires_key = False
    if not base_url:
        provider.is_configured = lambda: False  # type: ignore[method-assign]
    return provider
