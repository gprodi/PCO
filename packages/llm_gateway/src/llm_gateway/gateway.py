"""Gateway : choisit le modèle selon le profil matériel et enchaîne les fournisseurs en secours."""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from typing import Any, TypeVar

from loguru import logger
from pydantic import BaseModel, ValidationError

from llm_gateway.config import GatewaySettings
from llm_gateway.errors import LLMError, ProviderUnavailableError, StructuredOutputError
from llm_gateway.profiles import Profile, load_profile
from llm_gateway.providers.anthropic_provider import AnthropicProvider
from llm_gateway.providers.base import Provider
from llm_gateway.providers.fake import FakeProvider
from llm_gateway.providers.openai_compat import (
    gemini_provider,
    litellm_provider,
    ollama_provider,
)
from llm_gateway.schema_utils import extract_json
from llm_gateway.types import ChatRequest, ChatResult, ImageInput, Role

T = TypeVar("T", bound=BaseModel)


def _sniff_media_type(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


class Gateway:
    """Point d'entrée unique vers les LLM.

    Les compteurs ``stats`` (appels, échecs, fallbacks par fournisseur) sont exposés par les API
    sous forme de métriques Prometheus (C8 / C11 / C20).
    """

    def __init__(self, providers: list[Provider], profile: Profile) -> None:
        if not providers:
            raise LLMError("Aucun fournisseur configuré (voir LLM_CHAIN)")
        self.providers = providers
        self.profile = profile
        self.stats: Counter[str] = Counter()

    # ------------------------------------------------------------------ construction
    @classmethod
    def from_settings(cls, settings: GatewaySettings | None = None) -> Gateway:
        """Construit la chaîne de fournisseurs à partir de la configuration."""
        settings = settings or GatewaySettings()
        profile = load_profile(settings.llm_profile)
        factories = {
            "ollama": lambda: ollama_provider(settings.ollama_base_url, settings.llm_timeout_s),
            "gemini": lambda: gemini_provider(
                settings.gemini_api_key, settings.gemini_base_url, settings.llm_timeout_s
            ),
            "anthropic": lambda: AnthropicProvider(
                settings.anthropic_api_key, settings.anthropic_effort, settings.llm_timeout_s
            ),
            "litellm": lambda: litellm_provider(
                settings.litellm_base_url, settings.litellm_api_key, settings.llm_timeout_s
            ),
            "fake": FakeProvider,
        }
        providers: list[Provider] = []
        for name in settings.chain:
            if name not in factories:
                logger.warning("Fournisseur inconnu ignoré : {}", name)
                continue
            provider = factories[name]()
            if provider.is_configured():
                providers.append(provider)
            else:
                logger.info("Fournisseur {} non configuré : ignoré", name)
        return cls(providers, profile)

    @classmethod
    def from_env(cls) -> Gateway:
        """Alias de ``from_settings()`` lisant l'environnement / le fichier .env."""
        return cls.from_settings(GatewaySettings())

    @classmethod
    def fake(cls, provider: FakeProvider | None = None, profile: str = "cpu") -> Gateway:
        """Gateway de test, entièrement hors ligne."""
        return cls([provider or FakeProvider()], load_profile(profile))

    # ------------------------------------------------------------------ cœur
    def _model(self, provider: Provider, role: Role) -> str:
        if provider.name == "fake":
            return "fake-model"
        return self.profile.model_for(provider.name, role)

    def _run(self, request: ChatRequest) -> ChatResult:
        failures: list[str] = []
        for provider in self.providers:
            if request.images and not provider.supports_vision:
                continue
            model = self._model(provider, request.role)
            try:
                result = provider.chat(request, model)
            except ProviderUnavailableError as exc:
                logger.warning("{} indisponible ({}), fournisseur suivant", provider.name, exc)
                self.stats[f"failure:{provider.name}"] += 1
                failures.append(provider.name)
                continue
            self.stats[f"call:{provider.name}"] += 1
            if failures:
                self.stats["fallback"] += 1
            result.fallback_from = failures
            return result
        raise LLMError(f"Tous les fournisseurs ont échoué : {failures}")

    # ------------------------------------------------------------------ API publique
    def complete(
        self,
        prompt: str,
        *,
        role: Role = "text",
        system: str | None = None,
        images: list[bytes] | None = None,
        max_tokens: int = 4096,
        temperature: float | None = 0.2,
    ) -> ChatResult:
        """Requête texte (ou vision si ``images``) ; renvoie le résultat détaillé."""
        request = ChatRequest(
            prompt=prompt,
            role="vision" if images else role,
            system=system,
            images=[ImageInput(d, _sniff_media_type(d)) for d in images or []],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return self._run(request)

    def chat(self, prompt: str, **kwargs: Any) -> str:
        """Comme ``complete`` mais ne renvoie que le texte."""
        return self.complete(prompt, **kwargs).text

    def structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        role: Role = "text",
        system: str | None = None,
        images: list[bytes] | None = None,
        max_tokens: int = 4096,
        retries: int = 1,
    ) -> T:
        """Réponse JSON validée par un modèle Pydantic (avec une relance corrective)."""
        json_schema = schema.model_json_schema()
        instructions = (
            "Réponds UNIQUEMENT avec un objet JSON valide conforme à ce schéma, sans texte autour."
        )
        full_system = f"{system}\n\n{instructions}" if system else instructions
        current_prompt = prompt
        last_error: Exception | None = None
        for _attempt in range(retries + 1):
            request = ChatRequest(
                prompt=current_prompt,
                role="vision" if images else role,
                system=full_system,
                images=[ImageInput(d, _sniff_media_type(d)) for d in images or []],
                json_schema=json_schema,
                schema_name=schema.__name__,
                max_tokens=max_tokens,
                temperature=0.0,
            )
            result = self._run(request)
            try:
                return schema.model_validate(extract_json(result.text))
            except (ValueError, ValidationError) as exc:
                last_error = exc
                self.stats["structured_retry"] += 1
                current_prompt = (
                    f"{prompt}\n\nTa réponse précédente était invalide ({exc}). "
                    "Corrige-la en respectant strictement le schéma JSON."
                )
        raise StructuredOutputError(f"Sortie non conforme au schéma {schema.__name__}: {last_error}")

    def vision(self, prompt: str, images: list[bytes], **kwargs: Any) -> str:
        """Description d'image(s) par un modèle vision."""
        return self.complete(prompt, images=images, **kwargs).text

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embeddings via le premier fournisseur qui les supporte."""
        failures: list[str] = []
        for provider in self.providers:
            if not provider.supports_embeddings:
                continue
            try:
                vectors = provider.embed(texts, self._model(provider, "embed"))
            except (ProviderUnavailableError, NotImplementedError) as exc:
                failures.append(f"{provider.name}: {exc}")
                continue
            self.stats[f"embed:{provider.name}"] += 1
            return vectors
        raise LLMError(f"Aucun fournisseur d'embeddings disponible : {failures}")


@lru_cache(maxsize=1)
def get_gateway() -> Gateway:
    """Instance partagée (à utiliser comme dépendance FastAPI)."""
    return Gateway.from_env()
