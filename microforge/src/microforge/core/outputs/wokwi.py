"""Export Wokwi : ``diagram.json`` + fichiers du sketch, à coller dans un projet wokwi.com.

Les composants sans équivalent Wokwi (BME280, RC522, L298N…) sont listés dans ``missing``.
Simulation AVR possible hors ligne avec avr8js (PWA, phase 2).
"""

from __future__ import annotations

import re
from typing import Any

from microforge.core.allocator import Allocation
from microforge.core.catalog import Catalog
from microforge.core.models import BoardDef, ProjectSpec, SignalRole
from microforge.core.netlist import BOARD
from microforge.core.outputs.colors import wire_color

MCU_ID = "mcu"


def _ohms(value: str) -> str:
    m = re.match(r"([\d.]+)\s*(k?)", value)
    if not m:
        return value
    n = float(m.group(1)) * (1000 if m.group(2) else 1)
    return str(int(n))


def wokwi_diagram(
    spec: ProjectSpec, board: BoardDef, alloc: Allocation, catalog: Catalog
) -> dict[str, Any]:
    """Construit le diagram.json Wokwi."""
    missing: list[str] = []
    parts: list[dict[str, Any]] = []
    if board.wokwi.get("type"):
        parts.append({"type": board.wokwi["type"], "id": MCU_ID, "top": 0, "left": 0, "attrs": {}})
    else:
        missing.append(
            f"carte {board.name} (non simulée par Wokwi : choisir une carte équivalente)"
        )
    wokwi_pins: dict[str, dict[str, str]] = {}
    col = 0
    for inst in spec.parts:
        comp = catalog.component(inst.component)
        if comp.passive:
            continue
        if not comp.wokwi:
            missing.append(f"{inst.name} ({comp.name})")
            continue
        attrs = dict(comp.wokwi.get("attrs", {}))
        attrs.update(inst.attrs)
        parts.append(
            {
                "type": comp.wokwi["type"],
                "id": inst.name,
                "top": -260,
                "left": 40 + col * 160,
                "attrs": attrs,
            }
        )
        wokwi_pins[inst.name] = comp.wokwi.get("pins", {})
        col += 1
    rcol = 0
    for p in alloc.added_parts:
        for rid, value in ((p.name, p.value), (f"{p.name}_bas", p.value_low)):
            if value is None:
                continue
            parts.append(
                {
                    "type": "wokwi-resistor",
                    "id": rid,
                    "top": -110,
                    "left": 40 + rcol * 90,
                    "rotate": 90,
                    "attrs": {"value": _ohms(value)},
                }
            )
            wokwi_pins[rid] = {"1": "1", "2": "2"}
            rcol += 1

    board_pin_by_label = {bp.label: bp.wokwi or bp.label for bp in board.pins}
    rails = board.wokwi.get("rails", {})
    gnd = board.wokwi.get("gnd", "GND")

    has_board = bool(board.wokwi.get("type"))

    def endpoint(ref: str, pin: str) -> str | None:
        if ref == BOARD:
            if not has_board:
                return None
            if pin == "GND":
                return f"{MCU_ID}:{gnd}"
            if pin in rails:
                return f"{MCU_ID}:{rails[pin]}"
            return f"{MCU_ID}:{board_pin_by_label.get(pin, pin)}"
        mapping = wokwi_pins.get(ref)
        if mapping is None:
            return None
        return f"{ref}:{mapping.get(pin, pin)}"

    from microforge.core.netlist import build_nets

    connections: list[list[Any]] = []
    for net in build_nets(board, alloc):
        color = wire_color(
            net, board.rails.get(net.name.replace("_", ".")) or board.rails.get(net.name)
        )[2]
        nodes = [endpoint(n.ref, n.pin) for n in net.nodes]
        nodes = [n for n in nodes if n]
        # Étoile depuis le premier nœud (souvent la carte) : un fil par liaison.
        for other in nodes[1:]:
            connections.append([nodes[0], other, color, []])

    return {
        "version": 1,
        "author": "MicroForge",
        "editor": "wokwi",
        "parts": parts,
        "connections": connections,
        "dependencies": {},
        "microforge": {
            "missing_parts": missing,
            "board": board.id,
            "board_simulable": has_board,
            "project": spec.title,
        },
    }


def is_signal(role: SignalRole) -> bool:
    return role not in (SignalRole.POWER, SignalRole.GROUND)
