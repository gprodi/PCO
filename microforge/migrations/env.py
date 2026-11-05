"""Environnement Alembic : métadonnées SQLModel de api_data, URL lue dans MF_DATABASE_URL."""

from __future__ import annotations

import microforge.api_data.db  # noqa: F401 — enregistre les 14 tables dans SQLModel.metadata
from alembic import context
from microforge.api_data.db import get_engine
from microforge.common.settings import get_settings
from sqlmodel import SQLModel

target_metadata = SQLModel.metadata


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    """L'autogénération ignore les index trigrammes : créés hors métadonnées (PostgreSQL seulement)."""
    return not (type_ == "index" and name and name.endswith("_trgm"))


def run_migrations_offline() -> None:
    """Génère le SQL sans base (``alembic upgrade head --sql``) : sert au MPD du dossier E1."""
    context.configure(
        url=context.config.attributes.get("url") or get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = get_engine(context.config.attributes.get("url") or get_settings().database_url)
    with engine.connect() as connection:
        # render_as_batch : les ALTER TABLE passent aussi sur SQLite (développement, tests).
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
