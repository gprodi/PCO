"""Atelier virtuel : simulation du comportement d'un projet (logique transpilée + modèles de composants).

``simulation_payload`` produit tout ce que le moteur JavaScript ``static/mfsim.js`` attend : le code
transpilé, les instances de composants et la résolution des entrées analogiques de la carte.
"""

from __future__ import annotations

from functools import cache
from importlib import resources
from typing import Any

from microforge.core.catalog import Catalog
from microforge.core.missions import charge_atelier
from microforge.core.models import BuildResult, ProjectSpec
from microforge.sim.page import atelier_html
from microforge.sim.transpile import TranspileError, transpile

__all__ = [
    "TranspileError",
    "atelier_html",
    "atelier_payload",
    "missions_js",
    "runtime_js",
    "simulation_payload",
    "transpile",
    "wiring_payload",
]


@cache
def runtime_js() -> str:
    """Moteur de simulation (navigateur et Node)."""
    return resources.files("microforge.sim").joinpath("static/mfsim.js").read_text(encoding="utf-8")


@cache
def missions_js() -> str:
    """Suivi des missions de l'atelier (navigateur et Node)."""
    return (
        resources.files("microforge.sim").joinpath("static/missions.js").read_text(encoding="utf-8")
    )


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
        "missions": charge_atelier(spec.template_id),
    }


def wiring_payload(result: BuildResult) -> dict[str, Any]:
    """Branchements attendus (broche du composant -> broche de la carte) et description de la carte.

    Sert au mode « Je branche » de l'atelier : chaque choix de l'utilisateur est comparé au câblage
    calculé par le moteur, et un mauvais choix est expliqué à partir des capacités de la broche.
    """
    board = result.board
    gpio_label = {p.gpio: p.label for p in board.pins}
    via = {}
    for added in result.added_parts:
        if added.part and added.pin:
            via[(added.part, added.pin)] = f"via une résistance de {added.value} ({added.reason})"
    pins = [
        {
            "part": a.part,
            "pin": a.pin,
            "role": a.role.value,
            "expected": a.board_label,
            "note": a.note,
            "via": via.get((a.part, a.pin), ""),
        }
        for a in result.assignments
    ]
    labels = [{"label": name, "kind": "power", "volts": v} for name, v in board.rails.items()]
    labels.append({"label": "GND", "kind": "ground", "volts": 0})
    labels += [
        {
            "label": p.label,
            "kind": "gpio",
            "caps": list(p.caps),
            "inputOnly": p.input_only,
            "reserved": p.reserved,
            "strapping": p.strapping,
            "note": p.note,
        }
        for p in board.pins
    ]
    buses = {}
    for bus, mapping in (("i2c", board.default_i2c), ("spi", board.default_spi)):
        if mapping:
            buses[bus] = {k: gpio_label.get(v, str(v)) for k, v in mapping.items()}
    return {
        "pins": pins,
        "board": {
            "name": board.name,
            "logicV": board.logic_v,
            "wokwi": (board.wokwi or {}).get("type"),
            "labels": labels,
            "buses": buses,
        },
    }


def atelier_payload(catalog: Catalog, result: BuildResult) -> dict[str, Any]:
    """Tout ce que l'atelier affiche : simulation + branchements + éléments Wokwi des composants."""
    payload = simulation_payload(catalog, result.spec)
    payload["wiring"] = wiring_payload(result)
    for part in payload["parts"]:
        comp = catalog.components.get(part["component"])
        wk = (comp.wokwi if comp else None) or {}
        part["wokwi"] = wk.get("type")
        part["wokwiAttrs"] = wk.get("attrs", {})
        part["supply"] = list(comp.supply_v) if comp else None
    return payload
