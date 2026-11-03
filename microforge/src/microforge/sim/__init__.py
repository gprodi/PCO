"""Atelier virtuel : simulation du comportement d'un projet (logique transpilée + modèles de composants).

``simulation_payload`` produit tout ce que le moteur JavaScript ``static/mfsim.js`` attend : le code
transpilé, les instances de composants et la résolution des entrées analogiques de la carte.
"""

from __future__ import annotations

from functools import cache
from importlib import resources
from typing import Any

from microforge.core.catalog import Catalog
from microforge.core.models import ProjectSpec
from microforge.sim.transpile import TranspileError, transpile

__all__ = ["TranspileError", "runtime_js", "simulation_payload", "transpile"]


@cache
def runtime_js() -> str:
    """Moteur de simulation (navigateur et Node)."""
    return resources.files("microforge.sim").joinpath("static/mfsim.js").read_text(encoding="utf-8")


def simulation_payload(catalog: Catalog, spec: ProjectSpec) -> dict[str, Any]:
    board = catalog.boards[spec.board]
    parts = []
    for p in spec.parts:
        comp = catalog.components.get(p.component)
        parts.append(
            {
                "name": p.name,
                "component": p.component,
                "label": p.label or (comp.name if comp else p.component),
                "attrs": dict(p.attrs),
            }
        )
    return {
        "title": spec.title,
        "template": spec.template_id,
        "board": board.id,
        "boardName": board.name,
        "adcMax": 4095 if board.family == "esp32" else 1023,
        "wifi": spec.uses_wifi,
        "parts": parts,
        "extra": [
            {"component": e.component, "quantity": e.quantity, "note": e.note}
            for e in spec.bom_extra
        ],
        "code": transpile(catalog, spec),
    }
