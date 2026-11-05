"""index trigrammes pour la recherche « contient » des composants (PostgreSQL)

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-05 10:30:00

GET /v1/components?q= filtre par ``name ILIKE '%q%' OR id ILIKE '%q%' OR description ILIKE '%q%'`` :
un index B-tree ne sert pas une recherche « contient ». Mesure sur la base réelle (workflow
``collecte`` run 7, PostgreSQL 17.11, 99 325 composants) : 104,911 ms en lecture complète, 0,044 ms
avec un index GIN à trigrammes (pg_trgm) sur chacune des trois colonnes (lecture bitmap combinée).
PostgreSQL seulement : sous SQLite (développement, tests), la migration ne fait rien.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEXES = {
    "ix_composant_name_trgm": "name",
    "ix_composant_id_trgm": "id",
    "ix_composant_description_trgm": "description",
}


def _postgresql() -> bool:
    return op.get_context().dialect.name == "postgresql"


def upgrade() -> None:
    if not _postgresql():
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")  # extension « de confiance » depuis PG 13
    for name, column in INDEXES.items():
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {name} ON composant USING gin ({column} gin_trgm_ops)"
        )


def downgrade() -> None:
    if not _postgresql():
        return
    for name in INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
