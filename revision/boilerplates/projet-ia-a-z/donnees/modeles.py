"""Modèle physique (SQLModel) : des œuvres et leurs identifiants externes. Aucune donnée personnelle.

MCD : OEUVRE (1,n) — possède — (1,1) IDENTIFIANT_EXTERNE.
"""

from datetime import UTC, datetime

from sqlalchemy import Column, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def maintenant() -> datetime:
    return datetime.now(UTC)


class Oeuvre(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("cle_titre", "annee", name="uq_oeuvre_titre_annee"),)

    id: int | None = Field(default=None, primary_key=True)
    titre: str = Field(max_length=300)
    #: titre sans accents, ponctuation ni article : sert aux recherches et au dédoublonnage
    cle_titre: str = Field(max_length=300, index=True)
    annee: int | None = Field(default=None, index=True)
    auteur: str | None = Field(default=None, max_length=200)
    genre: str | None = Field(default=None, max_length=200)
    resume: str | None = Field(default=None, sa_column=Column(Text))
    note: float | None = Field(default=None, ge=0, le=10)
    #: champ → source (JSON) : traçabilité de la fusion
    provenance: str = Field(default="{}", sa_column=Column(Text, nullable=False))
    mis_a_jour: datetime = Field(default_factory=maintenant)


class IdentifiantExterne(SQLModel, table=True):
    __tablename__ = "identifiant_externe"

    source: str = Field(primary_key=True, max_length=50)
    valeur: str = Field(primary_key=True, max_length=200)
    oeuvre_id: int = Field(foreign_key="oeuvre.id", index=True)
