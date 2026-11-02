"""Configuration commune (variables d'environnement / .env) et journalisation loguru."""

from __future__ import annotations

import sys
from functools import lru_cache

from loguru import logger
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres de MicroForge. Voir ``microforge/.env.example``."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = Field(default="dev", alias="MF_ENV")
    database_url: str = Field(default="sqlite:///./microforge.db", alias="MF_DATABASE_URL")

    # JWT RS256 : api_data signe (clé privée), api_ia vérifie (clé publique).
    jwt_private_key: str | None = Field(default=None, alias="MF_JWT_PRIVATE_KEY")
    jwt_public_key: str | None = Field(default=None, alias="MF_JWT_PUBLIC_KEY")
    jwt_issuer: str = Field(default="microforge-api-data", alias="MF_JWT_ISSUER")
    jwt_audience: str = Field(default="microforge", alias="MF_JWT_AUDIENCE")
    access_minutes: int = Field(default=15, alias="MF_ACCESS_MINUTES")
    refresh_days: int = Field(default=7, alias="MF_REFRESH_DAYS")

    # Chiffrement des données personnelles (Fernet) + sel de l'index aveugle
    fernet_key: str | None = Field(default=None, alias="MF_FERNET_KEY")
    blind_index_salt: str = Field(default="change-me", alias="MF_BLIND_INDEX_SALT")

    cors_origins: str = Field(
        default="http://localhost:8501,http://localhost:5173", alias="MF_CORS_ORIGINS"
    )
    api_data_url: str = Field(default="http://localhost:8000", alias="MF_API_DATA_URL")
    api_ia_url: str = Field(default="http://localhost:8001", alias="MF_API_IA_URL")

    # Vision
    yolo_weights: str | None = Field(default=None, alias="MF_YOLO_WEIGHTS")
    mlflow_model_uri: str | None = Field(default=None, alias="MF_MLFLOW_MODEL_URI")
    max_upload_mb: int = Field(default=8, alias="MF_MAX_UPLOAD_MB")
    rate_limit_token: str = Field(default="10/minute", alias="MF_RATE_LIMIT_TOKEN")
    rate_limit_vision: str = Field(default="30/hour", alias="MF_RATE_LIMIT_VISION")

    log_level: str = Field(default="INFO", alias="MF_LOG_LEVEL")
    log_json: bool = Field(default=False, alias="MF_LOG_JSON")

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def setup_logging(service: str, settings: Settings | None = None) -> None:
    """Journalisation structurée (C20) : JSON en production, lisible en développement.

    Règle RGPD : on ne journalise JAMAIS d'e-mail, de mot de passe ni de token ; seulement
    l'identifiant utilisateur (pseudonyme) et l'identifiant de requête.
    """
    settings = settings or get_settings()
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        serialize=settings.log_json,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
        f"{service} | " + "{extra[request_id]} | {message}",
    )
    logger.configure(extra={"request_id": "-", "service": service})
