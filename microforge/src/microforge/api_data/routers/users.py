"""Compte utilisateur et droits RGPD (accès / portabilité / effacement)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from sqlmodel import Session, delete, select

from microforge.api_data.db import (
    Feedback,
    InventoryItem,
    MissionReussie,
    Photo,
    Project,
    RefreshToken,
    User,
    get_session,
)
from microforge.api_data.deps import current_user
from microforge.api_data.schemas import UserOut
from microforge.common.security import decrypt

router = APIRouter(prefix="/v1/users", tags=["utilisateurs"])


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user


@router.get("/me/export")
def export_me(
    user: User = Depends(current_user), session: Session = Depends(get_session)
) -> dict[str, Any]:
    """Droit d'accès et de portabilité (RGPD art. 15 et 20) : toutes les données de l'utilisateur."""
    return {
        "compte": {
            "pseudo": user.username,
            "email": decrypt(user.email_encrypted),
            "ville": user.city,
            "consentement_entrainement": user.consent_training,
            "cree_le": user.created_at.isoformat(),
            "derniere_connexion": user.last_login_at.isoformat() if user.last_login_at else None,
        },
        "inventaire": [
            i.model_dump(mode="json")
            for i in session.exec(select(InventoryItem).where(InventoryItem.user_id == user.id))
        ],
        "projets": [
            p.model_dump(mode="json")
            for p in session.exec(select(Project).where(Project.user_id == user.id))
        ],
        "photos": [
            p.model_dump(mode="json")
            for p in session.exec(select(Photo).where(Photo.user_id == user.id))
        ],
        "retours": [
            f.model_dump(mode="json")
            for f in session.exec(select(Feedback).where(Feedback.user_id == user.id))
        ],
        "missions_reussies": [
            m.model_dump(mode="json")
            for m in session.exec(select(MissionReussie).where(MissionReussie.user_id == user.id))
        ],
    }


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(user: User = Depends(current_user), session: Session = Depends(get_session)) -> None:
    """Droit à l'effacement (RGPD art. 17) : suppression définitive du compte et des données liées."""
    for model in (Feedback, Photo, InventoryItem, Project, MissionReussie, RefreshToken):
        session.exec(delete(model).where(model.user_id == user.id))  # type: ignore[arg-type]
    session.delete(user)
    session.commit()
