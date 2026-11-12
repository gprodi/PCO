"""Progression dans l'atelier virtuel : missions réussies, points, niveau, badges, parcours."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select

from microforge.api_data.db import MissionReussie, User, get_session
from microforge.api_data.deps import current_user
from microforge.api_data.schemas import MissionIn
from microforge.core import get_catalog
from microforge.core.progression import bilan, mission_existe

router = APIRouter(prefix="/v1", tags=["progression"])


def _faites(session: Session, user: User) -> list[tuple[str, str]]:
    lignes = session.exec(select(MissionReussie).where(MissionReussie.user_id == user.id))
    return [(m.template_id, m.mission_id) for m in lignes]


@router.get("/progression")
def lire(
    user: User = Depends(current_user), session: Session = Depends(get_session)
) -> dict[str, Any]:
    return bilan(_faites(session, user), get_catalog())


@router.post("/progression", status_code=201)
def enregistrer(
    body: MissionIn,
    response: Response,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Enregistre une mission réussie (idempotent : déjà réussie → 200, rien n'est dupliqué)."""
    catalog = get_catalog()
    if not mission_existe(body.template_id, body.mission_id, catalog):
        raise HTTPException(404, "Mission inconnue")
    deja = session.exec(
        select(MissionReussie).where(
            MissionReussie.user_id == user.id,
            MissionReussie.template_id == body.template_id,
            MissionReussie.mission_id == body.mission_id,
        )
    ).first()
    if deja is None:
        session.add(
            MissionReussie(
                user_id=user.id, template_id=body.template_id, mission_id=body.mission_id
            )
        )
        session.commit()
    else:
        response.status_code = 200
    return bilan(_faites(session, user), catalog)
