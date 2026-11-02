"""Inventaire de l'utilisateur (contrôle de propriété sur chaque objet — OWASP API1 BOLA)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from microforge.api_data.db import (
    Component,
    Feedback,
    InventoryItem,
    Photo,
    User,
    get_session,
    utcnow,
)
from microforge.api_data.deps import current_user
from microforge.api_data.schemas import (
    BulkInventoryIn,
    FeedbackIn,
    InventoryIn,
    InventoryOut,
    InventoryPatch,
    PhotoIn,
)

router = APIRouter(prefix="/v1", tags=["inventaire"])


def _owned(session: Session, item_id: int, user: User) -> InventoryItem:
    item = session.get(InventoryItem, item_id)
    # 404 (et pas 403) pour ne pas révéler l'existence de l'objet d'un autre utilisateur.
    if item is None or item.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Article introuvable")
    return item


def _check_component(session: Session, component_id: str) -> None:
    if session.get(Component, component_id) is None:
        raise HTTPException(422, f"Composant inconnu : {component_id}")


@router.get("/inventory", response_model=list[InventoryOut])
def list_inventory(
    user: User = Depends(current_user), session: Session = Depends(get_session)
) -> list[InventoryItem]:
    return list(
        session.exec(
            select(InventoryItem)
            .where(InventoryItem.user_id == user.id)
            .order_by(InventoryItem.component_id)
        )
    )


@router.get("/inventory/summary")
def inventory_summary(
    user: User = Depends(current_user), session: Session = Depends(get_session)
) -> dict[str, int]:
    """{composant: quantité totale} — format attendu par api_ia /v1/builds/suggest."""
    out: dict[str, int] = {}
    for item in session.exec(select(InventoryItem).where(InventoryItem.user_id == user.id)):
        out[item.component_id] = out.get(item.component_id, 0) + item.quantity
    return out


@router.post("/inventory", response_model=InventoryOut, status_code=201)
def add_item(
    body: InventoryIn, user: User = Depends(current_user), session: Session = Depends(get_session)
) -> InventoryItem:
    _check_component(session, body.component_id)
    existing = session.exec(
        select(InventoryItem).where(
            InventoryItem.user_id == user.id,
            InventoryItem.component_id == body.component_id,
            InventoryItem.location == body.location,
        )
    ).first()
    if existing:
        existing.quantity += body.quantity
        existing.updated_at = utcnow()
        item = existing
    else:
        item = InventoryItem(user_id=user.id, **body.model_dump())  # type: ignore[arg-type]
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.post("/inventory/bulk", response_model=list[InventoryOut])
def add_bulk(
    body: BulkInventoryIn,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> list[InventoryItem]:
    """Ajout groupé après validation d'une photo d'inventaire."""
    return [
        add_item(
            InventoryIn(**{**i.model_dump(), "location": i.location or body.location}),
            user,
            session,
        )
        for i in body.items
    ]


@router.patch("/inventory/{item_id}", response_model=InventoryOut)
def patch_item(
    item_id: int,
    body: InventoryPatch,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> InventoryItem:
    item = _owned(session, item_id, user)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    item.updated_at = utcnow()
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/inventory/{item_id}", status_code=204)
def delete_item(
    item_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)
) -> None:
    session.delete(_owned(session, item_id, user))
    session.commit()


@router.post("/photos", status_code=201)
def register_photo(
    body: PhotoIn, user: User = Depends(current_user), session: Session = Depends(get_session)
) -> dict[str, int]:
    """Enregistre les métadonnées d'une photo analysée (l'image elle-même n'est pas conservée)."""
    from datetime import date, timedelta

    photo = Photo(
        user_id=user.id, delete_after=date.today() + timedelta(days=30), **body.model_dump()
    )  # type: ignore[arg-type]
    session.add(photo)
    session.commit()
    session.refresh(photo)
    return {"id": photo.id}  # type: ignore[dict-item]


@router.post("/feedback", status_code=201)
def add_feedback(
    body: FeedbackIn, user: User = Depends(current_user), session: Session = Depends(get_session)
) -> dict[str, int]:
    """Retour sur une détection (correct / mauvaise étiquette / faux positif / oubli) — boucle MLOps."""
    if body.photo_id is not None:
        photo = session.get(Photo, body.photo_id)
        if photo is None or photo.user_id != user.id:
            raise HTTPException(404, "Photo introuvable")
    fb = Feedback(user_id=user.id, **body.model_dump())  # type: ignore[arg-type]
    session.add(fb)
    session.commit()
    session.refresh(fb)
    return {"id": fb.id}  # type: ignore[dict-item]
