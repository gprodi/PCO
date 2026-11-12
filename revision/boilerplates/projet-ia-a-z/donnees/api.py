"""API de données : seule porte d'accès à la base, joignable uniquement sur le réseau privé.

Chaque appel présente la clé de service ``X-API-Key`` (comparée en temps constant).
"""

import json
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, status
from prometheus_client import make_asgi_app
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import Session, select

from collecte.modele import Fiche
from collecte.normalise import cle_titre
from commun.config import get_settings
from commun.logs import configurer
from donnees.db import creer_tables, session
from donnees.modeles import IdentifiantExterne, Oeuvre, maintenant


@asynccontextmanager
async def cycle_de_vie(_: FastAPI) -> AsyncIterator[None]:
    configurer(json=get_settings().log_json)
    creer_tables()
    yield


app = FastAPI(title="API de données", version="0.1.0", lifespan=cycle_de_vie)
app.mount("/metrics", make_asgi_app())


def verifier_cle(x_api_key: Annotated[str | None, Header()] = None) -> None:
    attendue = get_settings().data_api_key
    if not attendue:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "APP_DATA_API_KEY non configurée")
    if not x_api_key or not secrets.compare_digest(x_api_key.encode(), attendue.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Clé de service invalide")


SessionDep = Annotated[Session, Depends(session)]
Protege = [Depends(verifier_cle)]


class OeuvreOut(BaseModel):
    id: int
    titre: str
    annee: int | None
    auteur: str | None
    genre: str | None
    resume: str | None
    note: float | None
    ids: dict[str, str] = Field(default_factory=dict)
    provenance: dict[str, str] = Field(default_factory=dict)


class Page(BaseModel):
    total: int
    elements: list[OeuvreOut]


class ImportOut(BaseModel):
    creees: int
    mises_a_jour: int


def _sortie(s: Session, o: Oeuvre) -> OeuvreOut:
    ids = s.exec(select(IdentifiantExterne).where(IdentifiantExterne.oeuvre_id == o.id)).all()
    return OeuvreOut(
        **o.model_dump(include={"id", "titre", "annee", "auteur", "genre", "resume", "note"}),
        ids={i.source: i.valeur for i in ids},
        provenance=json.loads(o.provenance),
    )


@app.get("/health")
def sante() -> dict[str, str]:
    return {"statut": "ok"}


@app.get("/oeuvres", response_model=Page, dependencies=Protege)
def lister(
    s: SessionDep,
    q: Annotated[str | None, Query(max_length=200)] = None,
    annee: int | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page:
    requete = select(Oeuvre)
    if q:
        # Paramètre lié : aucune concaténation SQL ; % et _ du texte saisi neutralisés.
        motif = cle_titre(q).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        requete = requete.where(Oeuvre.cle_titre.like(f"%{motif}%", escape="\\"))
    if annee is not None:
        requete = requete.where(Oeuvre.annee == annee)
    total = s.exec(select(func.count()).select_from(requete.subquery())).one()
    lignes = s.exec(requete.order_by(Oeuvre.id).offset(offset).limit(limit)).all()
    return Page(total=total, elements=[_sortie(s, o) for o in lignes])


@app.get("/oeuvres/{oeuvre_id}", response_model=OeuvreOut, dependencies=Protege)
def lire(oeuvre_id: int, s: SessionDep) -> OeuvreOut:
    oeuvre = s.get(Oeuvre, oeuvre_id)
    if oeuvre is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Œuvre inconnue")
    return _sortie(s, oeuvre)


def _retrouver(s: Session, fiche: Fiche) -> Oeuvre | None:
    for source, valeur in fiche.ids.items():
        lien = s.get(IdentifiantExterne, (source, valeur))
        if lien is not None:
            return s.get(Oeuvre, lien.oeuvre_id)
    cle = cle_titre(fiche.titre)
    return s.exec(select(Oeuvre).where(Oeuvre.cle_titre == cle, Oeuvre.annee == fiche.annee)).first()


@app.post("/oeuvres/import", response_model=ImportOut, dependencies=Protege)
def importer(fiches: Annotated[list[Fiche], Body(max_length=1000)], s: SessionDep) -> ImportOut:
    """Ajoute ou met à jour les fiches « gold » (idempotent : rejouer un import ne duplique rien)."""
    creees = mises_a_jour = 0
    for fiche in fiches:
        oeuvre = _retrouver(s, fiche)
        valeurs = fiche.model_dump(include={"titre", "annee", "auteur", "genre", "resume", "note"})
        if oeuvre is None:
            oeuvre = Oeuvre(**valeurs, cle_titre=cle_titre(fiche.titre))
            creees += 1
        else:
            for champ, valeur in valeurs.items():
                setattr(oeuvre, champ, valeur)
            oeuvre.cle_titre = cle_titre(fiche.titre)
            mises_a_jour += 1
        oeuvre.provenance = json.dumps(fiche.provenance, ensure_ascii=False)
        oeuvre.mis_a_jour = maintenant()
        s.add(oeuvre)
        s.flush()
        for source, valeur in fiche.ids.items():
            if s.get(IdentifiantExterne, (source, valeur)) is None:
                s.add(IdentifiantExterne(source=source, valeur=valeur, oeuvre_id=oeuvre.id))
    s.commit()
    return ImportOut(creees=creees, mises_a_jour=mises_a_jour)
