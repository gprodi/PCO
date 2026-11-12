"""missions de l'atelier réussies (progression, badges)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-12 09:30:00

Une ligne par mission réussie et par utilisateur (unique), effacée avec le compte (RGPD).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mission_reussie",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=False),
        sa.Column("template_id", sa.String(length=80), nullable=False),
        sa.Column("mission_id", sa.String(length=60), nullable=False),
        sa.Column("reussie_le", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "template_id", "mission_id", name="uq_mission_reussie"),
    )
    op.create_index("ix_mission_reussie_user_id", "mission_reussie", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_mission_reussie_user_id", table_name="mission_reussie")
    op.drop_table("mission_reussie")
