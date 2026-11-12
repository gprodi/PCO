"""Réglages lus dans l'environnement (fichier .env accepté). Aucun secret dans le code."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    domaine: str = "le catalogue"

    # --- API de données (réseau privé) ---
    database_url: str = "sqlite:///./donnees.db"
    data_api_url: str = "http://localhost:8000"
    #: clé partagée entre les deux API ; jamais exposée à l'interface
    data_api_key: str = Field(default="", repr=False)

    # --- API d'IA : comptes et jetons ---
    auth_database_url: str = "sqlite:///./comptes.db"
    secret_key: str = Field(default="", repr=False)
    access_minutes: int = 15
    refresh_days: int = 7
    login_rate: str = "10/minute"
    chat_rate: str = "30/minute"

    # --- Modèles (aucune API payante) ---
    ollama_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen3:4b"
    ollama_embed_model: str = "bge-m3"
    gemini_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    gemini_api_key: str = Field(default="", repr=False)
    gemini_model: str = "gemini-flash-latest"
    gemini_embed_model: str = "gemini-embedding-001"
    llm_timeout_s: float = 60.0

    # --- RAG ---
    #: vide : index en mémoire ; sinon postgresql+psycopg://… (pgvector)
    vector_url: str = ""
    rag_seuil: float = 0.25
    rag_k: int = 4

    # --- Web (outil de l'enquêteur, collecte) ---
    user_agent: str = "assistant-ia/0.1 (projet de formation)"
    wiki_lang: str = "fr"

    # --- Interface ---
    ia_api_url: str = "http://localhost:8001"

    log_json: bool = False

    @field_validator("secret_key")
    @classmethod
    def _secret_assez_long(cls, value: str) -> str:
        if value and len(value) < 32:
            raise ValueError(
                "APP_SECRET_KEY : 32 caractères au moins (python -c 'import secrets; print(secrets.token_urlsafe(48))')"
            )
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
