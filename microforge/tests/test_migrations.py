"""Les migrations Alembic créent exactement le schéma des modèles SQLModel (C4)."""

from __future__ import annotations

from pathlib import Path

import microforge.api_data.db  # noqa: F401
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlmodel import SQLModel

INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _config(url: str) -> Config:
    cfg = Config(str(INI))
    cfg.attributes["url"] = url
    return cfg


def test_upgrade_creates_all_tables_and_matches_models(tmp_path):
    url = f"sqlite:///{tmp_path / 'm.db'}"
    command.upgrade(_config(url), "head")
    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
    assert tables == set(SQLModel.metadata.tables)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), SQLModel.metadata)
    assert diff == [], f"modèles et migrations divergent : {diff}"


def test_downgrade_to_base_removes_tables(tmp_path):
    url = f"sqlite:///{tmp_path / 'm.db'}"
    cfg = _config(url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    assert set(inspect(create_engine(url)).get_table_names()) <= {"alembic_version"}
