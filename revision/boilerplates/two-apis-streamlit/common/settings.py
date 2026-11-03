"""Réglages partagés (variables d'environnement ou fichier .env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_key: str = "changer-moi"
    data_url: str = "http://127.0.0.1:8000"
    ia_url: str = "http://127.0.0.1:8001"
    database_url: str = "sqlite:///./avis.db"
    log_json: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
