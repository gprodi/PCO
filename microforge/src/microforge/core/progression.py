"""Progression de l'utilisateur : points, niveau, badges et avancement du parcours.

Calcul pur, à partir des missions réussies (couples modèle, mission) : l'API le refait à chaque
lecture, rien n'est stocké en double. La progression est déclarée par le navigateur (missions
validées par le simulateur côté client) : c'est un outil d'apprentissage, pas une certification.
"""

from __future__ import annotations

from collections.abc import Iterable
from functools import cache
from importlib import resources
from typing import Any

import yaml

from microforge.core.catalog import Catalog
from microforge.core.ideas import load_path, load_themes
from microforge.core.missions import missions_du_modele, missions_ecrites

NIVEAUX = (
    (0, "Apprenti"),
    (100, "Bricoleur"),
    (300, "Maker"),
    (700, "Inventeur"),
    (1500, "Ingénieur"),
)


@cache
def badges() -> tuple[dict[str, Any], ...]:
    texte = (
        resources.files("microforge.core").joinpath("data/badges.yaml").read_text(encoding="utf-8")
    )
    return tuple(yaml.safe_load(texte))


@cache
def _themes_des_modeles() -> dict[str, set[str]]:
    sortie: dict[str, set[str]] = {}
    for theme in load_themes():
        for idee in theme.idees:
            if idee.template:
                sortie.setdefault(idee.template, set()).add(theme.id)
    return sortie


def mission_existe(template_id: str, mission_id: str, catalog: Catalog) -> bool:
    return template_id in catalog.templates and any(
        m.id == mission_id for m in missions_du_modele(template_id)
    )


def niveau(xp: int) -> dict[str, Any]:
    courant = max((n for n in NIVEAUX if xp >= n[0]), key=lambda n: n[0])
    suivants = [n for n in NIVEAUX if n[0] > xp]
    return {
        "nom": courant[1],
        "xp_niveau": courant[0],
        "prochain": suivants[0][1] if suivants else None,
        "xp_prochain": suivants[0][0] if suivants else None,
    }


def bilan(faites: Iterable[tuple[str, str]], catalog: Catalog) -> dict[str, Any]:
    """Points, niveau, badges (obtenus ou non) et avancement de chaque étape du parcours."""
    faites = {(t, m) for t, m in faites if mission_existe(t, m, catalog)}
    index = {(t, m.id): m for t in {t for t, _ in faites} for m in missions_du_modele(t)}
    xp = sum(index[f].xp(catalog.templates[f[0]].difficulty) for f in faites)

    etapes = []
    for etape in load_path():
        dues = [(t, m.id) for t in etape.templates for m in missions_ecrites().get(t, ())]
        etapes.append(
            {
                "etape": etape.etape,
                "titre": etape.titre,
                "total": len(dues),
                "faites": sum(1 for d in dues if d in faites),
                "prochaine": next(
                    ({"template_id": t, "mission_id": m} for t, m in dues if (t, m) not in faites),
                    None,
                ),
            }
        )
    themes = {th for t, _ in faites for th in _themes_des_modeles().get(t, ())}

    def obtenu(regle: dict[str, Any]) -> bool:
        if "missions" in regle:
            return len(faites) >= regle["missions"]
        if "mission" in regle:
            return sum(1 for _, m in faites if m == regle["mission"]) >= regle["projets"]
        if "etape" in regle:
            e = next(x for x in etapes if x["etape"] == regle["etape"])
            return e["total"] > 0 and e["faites"] == e["total"]
        if "themes" in regle:
            return len(themes) >= regle["themes"]
        if "xp" in regle:
            return xp >= regle["xp"]
        raise ValueError(f"règle de badge inconnue : {regle}")

    return {
        "xp": xp,
        "niveau": niveau(xp),
        "missions": sorted(
            [{"template_id": t, "mission_id": m} for t, m in faites],
            key=lambda x: (x["template_id"], x["mission_id"]),
        ),
        "badges": [
            {**{k: b[k] for k in ("id", "titre", "description")}, "obtenu": obtenu(b["regle"])}
            for b in badges()
        ],
        "etapes": etapes,
        "prochaine": next((e["prochaine"] for e in etapes if e["prochaine"]), None),
    }
