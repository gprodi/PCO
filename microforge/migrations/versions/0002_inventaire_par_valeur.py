"""inventaire par valeur (résistances, condensateurs… : 10 × 220 Ω ≠ 10 × 10 kΩ)

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-03 10:00:00

Ajoute ``article_inventaire.value`` (0 = composant sans valeur) et remplace la contrainte
d'unicité (utilisateur, composant, emplacement) par (utilisateur, composant, valeur, emplacement).
La contrainte de la révision 0001 n'a pas de nom : sous SQLite, une convention de nommage lui en
donne un le temps de la recréation de la table (mode batch) ; sous PostgreSQL, son nom est lu.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "article_inventaire"
OLD_COLS = ["user_id", "component_id", "location"]
NEW_COLS = ["user_id", "component_id", "value", "location"]
NEW_NAME = "uq_inventaire_composant_valeur"
CONVENTION = {"uq": "uq_%(table_name)s_%(column_0_N_name)s"}
SQLITE_OLD_NAME = "uq_article_inventaire_user_id_component_id_location"


#: Nom donné par PostgreSQL à la contrainte sans nom de 0001 (table_colonnes_key), vérifié sur une base.
POSTGRES_OLD_NAME = "article_inventaire_user_id_component_id_location_key"


def _old_name() -> str:
    dialect = op.get_context().dialect.name
    if dialect == "sqlite":
        return SQLITE_OLD_NAME
    if context.is_offline_mode():  # « alembic upgrade head --sql » : pas de base à inspecter
        return POSTGRES_OLD_NAME
    bind = op.get_bind()
    for uq in sa.inspect(bind).get_unique_constraints(TABLE):
        if uq["column_names"] == OLD_COLS:
            return uq["name"]
    raise RuntimeError("contrainte d'unicité de la révision 0001 introuvable")


def upgrade() -> None:
    old = _old_name()
    with op.batch_alter_table(TABLE, naming_convention=CONVENTION) as batch_op:
        batch_op.add_column(sa.Column("value", sa.Float(), nullable=False, server_default="0"))
        batch_op.drop_constraint(old, type_="unique")
        batch_op.create_unique_constraint(NEW_NAME, NEW_COLS)


def downgrade() -> None:
    # Sans valeur, plusieurs lignes deviennent identiques (220 Ω et 10 kΩ du même tiroir) :
    # on les fusionne (quantités additionnées) avant de rétablir l'ancienne contrainte.
    group = "user_id, component_id, location"
    op.execute(
        f"UPDATE {TABLE} SET quantity = (SELECT SUM(q.quantity) FROM {TABLE} q "  # noqa: S608
        f"WHERE q.user_id = {TABLE}.user_id AND q.component_id = {TABLE}.component_id "
        f"AND q.location = {TABLE}.location) "
        f"WHERE id IN (SELECT MIN(id) FROM {TABLE} GROUP BY {group})"
    )
    op.execute(
        f"DELETE FROM {TABLE} WHERE id NOT IN (SELECT MIN(id) FROM {TABLE} GROUP BY {group})"  # noqa: S608
    )
    with op.batch_alter_table(TABLE, naming_convention=CONVENTION) as batch_op:
        batch_op.drop_constraint(NEW_NAME, type_="unique")
        batch_op.drop_column("value")
        batch_op.create_unique_constraint(SQLITE_OLD_NAME, OLD_COLS)
