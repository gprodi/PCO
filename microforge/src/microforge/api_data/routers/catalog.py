"""Catalogue : composants, cartes, offres fournisseurs, modèles de projets (lecture authentifiée)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, col, or_, select

from microforge.api_data.db import Component, Offer, Supplier, User, get_session
from microforge.api_data.deps import current_user
from microforge.api_data.schemas import ComponentDetail, ComponentOut, OfferOut
from microforge.core.catalog import get_catalog

router = APIRouter(prefix="/v1", tags=["catalogue"])


@router.get("/components", response_model=list[ComponentOut])
def list_components(
    q: str | None = Query(default=None, max_length=60),
    category: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    _user: User = Depends(current_user),
) -> list[Component]:
    stmt = select(Component)
    if category:
        stmt = stmt.where(Component.category_id == category)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                col(Component.name).ilike(like),
                col(Component.id).ilike(like),
                col(Component.description).ilike(like),
            )
        )
    return list(
        session.exec(stmt.order_by(Component.category_id, Component.id).offset(offset).limit(limit))
    )


@router.get("/components/{component_id}", response_model=ComponentDetail)
def get_component(
    component_id: str, session: Session = Depends(get_session), _user: User = Depends(current_user)
) -> ComponentDetail:
    row = session.get(Component, component_id)
    if row is None:
        raise HTTPException(404, "Composant introuvable")
    detail = ComponentDetail.model_validate(row, from_attributes=True)
    cat = get_catalog()
    if component_id in cat.components:
        comp = cat.components[component_id]
        detail.pins = [p.model_dump(mode="json") for p in comp.pins]
        detail.libraries = sorted({lib for t in comp.code.values() for lib in t.libraries})
        detail.notes = comp.notes
    elif component_id in cat.boards:
        board = cat.boards[component_id]
        detail.pins = [p.model_dump(mode="json") for p in board.pins]
        detail.notes = board.notes
    return detail


@router.get("/components/{component_id}/offers", response_model=list[OfferOut])
def component_offers(
    component_id: str, session: Session = Depends(get_session), _user: User = Depends(current_user)
) -> list[OfferOut]:
    rows = session.exec(
        select(Offer, Supplier)
        .join(Supplier)
        .where(Offer.component_id == component_id)
        .order_by(Offer.unit_price_eur)
    )
    return [
        OfferOut(
            supplier=s.name,
            unit_price_eur=o.unit_price_eur,
            stock=o.stock,
            url=o.url,
            collected_at=o.collected_at,
        )
        for o, s in rows
    ]


@router.get("/boards", response_model=list[ComponentOut])
def list_boards(
    session: Session = Depends(get_session), _user: User = Depends(current_user)
) -> list[Component]:
    return list(session.exec(select(Component).where(Component.category_id == "carte")))


@router.get("/templates")
def list_templates(_user: User = Depends(current_user)) -> list[dict]:
    cat = get_catalog()
    return [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "difficulty": t.difficulty,
            "tags": t.tags,
            "requires_wifi": t.requires_wifi,
            "parts": [p.model_dump() for p in t.parts],
        }
        for t in cat.templates.values()
    ]
