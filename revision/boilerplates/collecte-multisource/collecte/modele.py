"""Format commun des enregistrements, quelle que soit leur source."""

from pydantic import BaseModel, Field


class Enregistrement(BaseModel):
    """Une œuvre telle qu'une source la décrit, déjà normalisée (dates, textes, notes)."""

    source: str
    titre: str
    annee: int | None = None
    auteur: str | None = None
    genre: str | None = None
    resume: str | None = None
    note: float | None = Field(default=None, ge=0, le=10)
    #: identifiants externes : {"openlibrary": "/works/OL…", "ref_catalogue": "OEU-001"}
    ids: dict[str, str] = Field(default_factory=dict)
    url: str | None = None


class Fiche(BaseModel):
    """Œuvre « gold » après fusion : un seul exemplaire, chaque champ avec sa source."""

    titre: str
    annee: int | None = None
    auteur: str | None = None
    genre: str | None = None
    resume: str | None = None
    note: float | None = None
    ids: dict[str, str] = Field(default_factory=dict)
    #: champ → source qui l'a fourni (traçabilité de la fusion)
    provenance: dict[str, str] = Field(default_factory=dict)
    sources: list[str] = Field(default_factory=list)
