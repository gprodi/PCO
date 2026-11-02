"""Configuration par variables d'environnement (.env supporté)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    """Paramètres du gateway. Aucun secret n'est codé en dur : tout vient de l'environnement."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_chain: str = Field(default="ollama,gemini,anthropic", alias="LLM_CHAIN")
    llm_profile: str | None = Field(default=None, alias="LLM_PROFILE")
    llm_timeout_s: float = Field(default=120.0, alias="LLM_TIMEOUT_S")

    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")

    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai",
        alias="GEMINI_BASE_URL",
    )

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_effort: str = Field(default="medium", alias="ANTHROPIC_EFFORT")

    litellm_base_url: str | None = Field(default=None, alias="LITELLM_BASE_URL")
    litellm_api_key: str | None = Field(default=None, alias="LITELLM_API_KEY")

    @property
    def chain(self) -> list[str]:
        """Liste ordonnée des fournisseurs à essayer."""
        return [p.strip().lower() for p in self.llm_chain.split(",") if p.strip()]
