"""Projets sauvegardés et liste d'achat (BOM − inventaire, offres les moins chères)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from microforge.api_data.db import (
    Component,
    InventoryItem,
    Offer,
    Project,
    Supplier,
    User,
    get_session,
)
from microforge.api_data.deps import current_user
from microforge.api_data.schemas import ProjectIn, ProjectOut, ShoppingIn
from microforge.core.builder import ProjectBuilder
from microforge.core.models import ProjectSpec
from microforge.core.outputs.bom import Offer as CoreOffer
from microforge.core.outputs.bom import shopping_list

router = APIRouter(prefix="/v1", tags=["projets"])


def _owned(session: Session, project_id: int, user: User) -> Project:
    project = session.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(404, "Projet introuvable")
    return project


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(
    user: User = Depends(current_user), session: Session = Depends(get_session)
) -> list[Project]:
    return list(
        session.exec(
            select(Project).where(Project.user_id == user.id).order_by(Project.created_at.desc())
        )
    )  # type: ignore[attr-defined]


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(
    body: ProjectIn, user: User = Depends(current_user), session: Session = Depends(get_session)
) -> Project:
    spec = ProjectSpec.model_validate(body.spec)  # validation complète de la spec
    if session.get(Component, body.board_id) is None:
        raise HTTPException(422, "Carte inconnue")
    project = Project(
        user_id=user.id,  # type: ignore[arg-type]
        title=body.title,
        board_id=body.board_id,
        template_id=body.template_id,
        spec_json=spec.model_dump_json(),
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.get("/projects/{project_id}")
def get_project(
    project_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)
) -> dict:
    project = _owned(session, project_id, user)
    return {
        **ProjectOut.model_validate(project).model_dump(mode="json"),
        "spec": json.loads(project.spec_json),
    }


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(
    project_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)
) -> None:
    session.delete(_owned(session, project_id, user))
    session.commit()


@router.post("/shopping-list")
def shopping(
    body: ShoppingIn, user: User = Depends(current_user), session: Session = Depends(get_session)
) -> dict:
    """Ce qu'il manque pour un projet sauvegardé ou un modèle, chiffré avec les offres collectées (E1)."""
    builder = ProjectBuilder()
    if body.project_id is not None:
        spec = ProjectSpec.model_validate_json(_owned(session, body.project_id, user).spec_json)
    elif body.template_id and body.board_id:
        if body.template_id not in builder.catalog.templates:
            raise HTTPException(404, "Modèle inconnu")
        spec = builder.spec_from_template(body.template_id, body.board_id)
    else:
        raise HTTPException(422, "project_id, ou template_id + board_id, requis")
    result = builder.build(spec)
    inventory: dict[str, int] = {}
    for item in session.exec(select(InventoryItem).where(InventoryItem.user_id == user.id)):
        inventory[item.component_id] = inventory.get(item.component_id, 0) + item.quantity
    ids = {line.component for line in result.bom}
    offers = [
        CoreOffer(
            supplier=s.name,
            component=o.component_id,
            unit_price_eur=o.unit_price_eur,
            url=o.url,
            stock=o.stock,
        )
        for o, s in session.exec(
            select(Offer, Supplier).join(Supplier).where(Offer.component_id.in_(ids))
        )  # type: ignore[attr-defined]
    ]
    sl = shopping_list(result.bom, inventory, offers)
    return {
        "project": spec.title,
        "lines": [line.model_dump() | {"subtotal": line.subtotal} for line in sl.lines],
        "to_buy": [line.model_dump() | {"subtotal": line.subtotal} for line in sl.to_buy],
        "by_supplier": {k: [line.component for line in v] for k, v in sl.by_supplier().items()},
        "total_eur": sl.total_eur,
        "markdown": sl.to_markdown(),
    }
