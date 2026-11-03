"""Réglages lus dans l'environnement (fichier .env en développement)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    secret_key: str = Field(min_length=32)  # openssl rand -hex 32 ; jamais dans le code
    database_url: str = "sqlite:///./app.db"
    access_minutes: int = 15
    refresh_days: int = 7
    login_rate: str = "5/minute"


@lru_cache
def get_settings() -> Settings:
    return Settings()
