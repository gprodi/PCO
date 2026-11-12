"""Missions de l'atelier virtuel : défis validés par le simulateur (``sim/static/missions.js``).

Chaque modèle a deux missions automatiques (brancher sans aide, une minute sans panne) ; les
modèles du parcours ont en plus des missions écrites à la main (``data/missions.yaml``).
"""

from __future__ import annotations

from functools import cache
from importlib import resources
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

OPERATEURS = {"==", "!=", "<", "<=", ">", ">="}


class Mission(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    titre: str
    consigne: str
    indice: str = ""
    action: dict[str, Any] | None = None
    attendu: dict[str, Any] | None = None
    fenetre_ms: int = Field(default=3000, gt=0)
    apres: str | None = None
    auto: Literal["branchement", "simulation"] | None = None
    duree_ms: int | None = None
    #: réglages des tests automatiques (non envoyés au navigateur)
    reglages_test: dict[str, Any] = Field(default_factory=dict, exclude=True)

    @model_validator(mode="before")
    @classmethod
    def _essais(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            data["reglages_test"] = {k: data.pop(k) for k in ("test_ms", "repete_ms") if k in data}
        return data

    @model_validator(mode="after")
    def _coherence(self) -> Mission:
        if self.auto is None and (self.action is None or self.attendu is None):
            raise ValueError(f"{self.id} : action et attendu obligatoires")
        for bloc in (self.action, self.attendu):
            for cond in _feuilles(bloc):
                if "op" in cond and cond["op"] not in OPERATEURS:
                    raise ValueError(f"{self.id} : opérateur inconnu {cond['op']}")
        return self

    def parties(self) -> set[str]:
        """Composants cités par l'action et le résultat attendu."""
        noms = {c["part"] for c in _feuilles(self.action) + _feuilles(self.attendu) if "part" in c}
        noms |= {c["charge"] for c in _feuilles(self.attendu) if "charge" in c}
        return noms

    def xp(self, difficulte: int) -> int:
        """Points gagnés : 5 pour une mission automatique, 10 par niveau de difficulté sinon."""
        return 5 if self.auto else 10 * max(1, difficulte)


def _feuilles(bloc: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not bloc:
        return []
    if "tous" in bloc:
        return [f for sous in bloc["tous"] for f in _feuilles(sous)]
    return [bloc]


AUTOMATIQUES = (
    Mission(
        id="brancher-sans-aide",
        titre="Câbler sans aide",
        consigne="Branche chaque broche toi-même, sans le bouton « Tout brancher » : l'atelier explique chaque erreur.",
        indice="Les broches d'alimentation vont sur 3V3 ou 5V selon le module, les masses sur GND.",
        auto="branchement",
    ),
    Mission(
        id="simulation-60s",
        titre="Une minute sans panne",
        consigne="Tout branché, laisse tourner la simulation 60 secondes (accélère ×10 ou ×60).",
        auto="simulation",
        duree_ms=60000,
    ),
)


@cache
def missions_ecrites() -> dict[str, tuple[Mission, ...]]:
    texte = (
        resources.files("microforge.core")
        .joinpath("data/missions.yaml")
        .read_text(encoding="utf-8")
    )
    brut = yaml.safe_load(texte) or {}
    sortie = {}
    for modele, liste in brut.items():
        missions = tuple(Mission.model_validate(m) for m in liste)
        ids = [m.id for m in missions]
        if len(ids) != len(set(ids)) or set(ids) & {m.id for m in AUTOMATIQUES}:
            raise ValueError(f"{modele} : identifiants de mission en double")
        for m in missions:
            if m.apres and m.apres not in ids[: ids.index(m.id)]:
                raise ValueError(f"{modele}/{m.id} : « apres » doit citer une mission précédente")
        sortie[modele] = missions
    return sortie


def missions_du_modele(template_id: str | None) -> list[Mission]:
    """Missions automatiques puis missions écrites du modèle (aucune écrite hors modèle)."""
    return [*AUTOMATIQUES, *missions_ecrites().get(template_id or "", ())]


def charge_atelier(template_id: str | None) -> list[dict[str, Any]]:
    """Missions telles que l'atelier les reçoit (sans les réglages de test)."""
    return [m.model_dump(exclude_none=True) for m in missions_du_modele(template_id)]
