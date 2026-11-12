"""Connexion à la base (SQLite en développement, PostgreSQL dans docker compose)."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

from commun.config import get_settings
from donnees import modeles  # noqa: F401 - enregistre les tables


@lru_cache
def moteur() -> Engine:
    url = get_settings().database_url
    options = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=options, pool_pre_ping=True)


def creer_tables() -> None:
    SQLModel.metadata.create_all(moteur())


def session() -> Iterator[Session]:
    with Session(moteur()) as s:
        yield s
