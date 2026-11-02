"""Idées de projets par thème (« Explorer par thème ») : plantes, intérieur, extérieur, sécurité…

Chaque idée est soit un **modèle générable** (template du catalogue), soit une **idée à concevoir par
l'IA** (``/v1/builds/from-goal`` avec la description et les composants suggérés). Avec un inventaire,
on indique ce qui est réalisable tout de suite et ce qu'il manque.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from importlib import resources
from typing import Any

import yaml
from pydantic import BaseModel, Field

from microforge.core.catalog import Catalog, get_catalog


class Idea(BaseModel):
    titre: str
    description: str
    difficulte: int = Field(default=1, ge=1, le=3)
    composants: list[str]
    template: str | None = None
    wifi: bool = False


class Theme(BaseModel):
    id: str
    titre: str
    icone: str
    description: str
    idees: list[Idea]


@lru_cache(maxsize=1)
def load_themes() -> list[Theme]:
    text = (
        resources.files("microforge.core.data").joinpath("idees.yaml").read_text(encoding="utf-8")
    )
    return [Theme.model_validate(t) for t in yaml.safe_load(text)["themes"]]


def explore(
    inventory: dict[str, int] | None = None, catalog: Catalog | None = None
) -> list[dict[str, Any]]:
    """Thèmes et idées, annotés avec le stock (composants manquants, carte possédée)."""
    catalog = catalog or get_catalog()
    inv: Counter[str] = Counter()
    for ref, qty in (inventory or {}).items():
        key = catalog.resolve(ref)
        if key:
            inv[key] += int(qty)
    boards = [b for b in inv if b in catalog.boards]
    out = []
    for theme in load_themes():
        ideas = []
        for idea in theme.idees:
            missing = sorted({c for c in idea.composants if inv.get(c, 0) == 0})
            board_ok = any(catalog.boards[b].wifi for b in boards) if idea.wifi else bool(boards)
            ideas.append(
                {
                    **idea.model_dump(),
                    "composants_noms": [catalog.component(c).name for c in idea.composants],
                    "generable": idea.template is not None,
                    "manquants": missing if inventory is not None else None,
                    "carte_ok": board_ok if inventory is not None else None,
                    "realisable": (not missing and board_ok) if inventory is not None else None,
                }
            )
        ideas.sort(
            key=lambda i: (
                not i["realisable"] if inventory is not None else False,
                i["difficulte"],
                i["titre"],
            )
        )
        out.append({**theme.model_dump(exclude={"idees"}), "idees": ideas})
    return out


def goal_for(idea: Idea | dict[str, Any]) -> str:
    """Texte « je veux construire » envoyé à l'IA pour une idée sans modèle."""
    d = idea if isinstance(idea, dict) else idea.model_dump()
    return f"{d['titre']} : {d['description']} Composants suggérés : {', '.join(d['composants'])}."
