"""index composite (catégorie, id) à la place de l'index sur la seule catégorie

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-05 09:30:00

Décision prise sur mesure (``mf-pipeline bench-index``, workflow ``collecte`` run 6, PostgreSQL 17,
99 325 composants) : pour ``WHERE category_id = :c ORDER BY category_id, id LIMIT 50``
(GET /v1/components?category=…), l'index sur la seule catégorie rend la requête plus lente que sans
index (3,718 ms contre 2,275 ms : lecture de toute la catégorie puis tri) ; l'index composite sert
le filtre et le tri en une seule lecture ordonnée (0,034 ms). Il couvre aussi les recherches par
catégorie seule (colonne de tête) : l'ancien index devient inutile.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_composant_category_id_id", "composant", ["category_id", "id"])
    op.drop_index("ix_composant_category_id", table_name="composant")


def downgrade() -> None:
    op.create_index("ix_composant_category_id", "composant", ["category_id"])
    op.drop_index("ix_composant_category_id_id", table_name="composant")
