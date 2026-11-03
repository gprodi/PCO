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


def test_inventory_value_migration_keeps_existing_rows(tmp_path):
    """0001 -> 0002 sur une base remplie : la ligne garde sa quantité, valeur 0 par défaut ;
    le même composant peut ensuite exister sous deux valeurs, pas deux fois sous la même."""
    import pytest
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    url = f"sqlite:///{tmp_path / 'm.db'}"
    cfg = _config(url)
    command.upgrade(cfg, "0001")
    engine = create_engine(url)
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO utilisateur (id, username, email_encrypted, email_index, "
                "password_hash, role, consent_training, is_active, created_at) "
                "VALUES (1, 'g', 'e', 'h', 'p', 'user', 0, 1, '2026-11-03')"
            )
        )
        c.execute(text("INSERT INTO categorie (id, label) VALUES ('passif', 'Passifs')"))
        c.execute(
            text(
                "INSERT INTO composant (id, name, category_id, description, interfaces, "
                "source, updated_at) VALUES ('resistor', 'R', 'passif', '', '', 'c', '2026-11-03')"
            )
        )
        c.execute(
            text(
                "INSERT INTO article_inventaire (user_id, component_id, quantity, location, "
                "note, updated_at) VALUES (1, 'resistor', 20, 'tiroir A', '', '2026-11-03')"
            )
        )
    command.upgrade(cfg, "head")
    insert = text(
        "INSERT INTO article_inventaire (user_id, component_id, value, quantity, location, "
        "note, updated_at) VALUES (1, 'resistor', :v, 5, 'tiroir A', '', '2026-11-03')"
    )
    with engine.begin() as c:
        assert c.execute(text("SELECT quantity, value FROM article_inventaire")).one() == (20, 0.0)
        c.execute(insert, {"v": 220.0})
    with pytest.raises(IntegrityError), engine.begin() as c:
        c.execute(insert, {"v": 220.0})
    command.downgrade(cfg, "0001")  # les deux lignes fusionnent : 20 + 5
    with engine.begin() as c:
        assert c.execute(text("SELECT quantity FROM article_inventaire")).scalars().all() == [25]
