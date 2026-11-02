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


class Showcase(BaseModel):
    """Projet open source réel de la vitrine (« ce que les makers construisent »)."""

    nom: str
    url: str
    categorie: str
    carte: str
    description: str
    commencer_par: list[str] = Field(default_factory=list)


class Step(BaseModel):
    """Étape du parcours de progression."""

    etape: int
    titre: str
    objectif: str
    notions: list[str]
    templates: list[str]


def _data(name: str) -> Any:
    return yaml.safe_load(
        resources.files("microforge.core.data").joinpath(name).read_text(encoding="utf-8")
    )


@lru_cache(maxsize=1)
def load_showcase() -> list[Showcase]:
    return [Showcase.model_validate(x) for x in _data("vitrine.yaml")]


@lru_cache(maxsize=1)
def load_path() -> list[Step]:
    return [Step.model_validate(x) for x in _data("parcours.yaml")]


def inspiration(catalog: Catalog | None = None) -> dict[str, Any]:
    """Parcours de progression + vitrine de vrais projets + chiffres clés (page d'accueil « envie »)."""
    catalog = catalog or get_catalog()

    def tpl(tid: str) -> dict[str, Any]:
        t = catalog.templates[tid]
        return {
            "id": tid,
            "titre": t.title,
            "difficulte": t.difficulty,
            "description": t.description,
        }

    themes = load_themes()
    return {
        "chiffres": {
            "modeles_generables": len(catalog.templates),
            "idees": sum(len(t.idees) for t in themes),
            "themes": len(themes),
            "composants": len(catalog.components),
            "cartes": len(catalog.boards),
        },
        "parcours": [
            {**s.model_dump(exclude={"templates"}), "projets": [tpl(t) for t in s.templates]}
            for s in load_path()
        ],
        "vitrine": [
            {
                **v.model_dump(exclude={"commencer_par"}),
                "commencer_par": [tpl(t) for t in v.commencer_par],
            }
            for v in load_showcase()
        ],
    }


def goal_for(idea: Idea | dict[str, Any]) -> str:
    """Texte « je veux construire » envoyé à l'IA pour une idée sans modèle."""
    d = idea if isinstance(idea, dict) else idea.model_dump()
    return f"{d['titre']} : {d['description']} Composants suggérés : {', '.join(d['composants'])}."
