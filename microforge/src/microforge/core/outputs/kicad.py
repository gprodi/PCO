"""Export d'une netlist KiCad (format S-expression « export », version E, KiCad 6 à 9).

Import : éditeur de PCB KiCad -> Fichier -> Importer -> Netlist. La carte de développement est
représentée par des barrettes femelles (J1) : on la monte sur supports, comme sur la plaque à
pastilles. Les modules sont des connecteurs (barrettes 2,54 mm) dont la broche n correspond à la
n-ième broche du module dans le catalogue.
"""

from __future__ import annotations

from datetime import UTC, datetime

from microforge.core.allocator import Allocation
from microforge.core.catalog import Catalog
from microforge.core.models import BoardDef, Net, ProjectSpec
from microforge.core.netlist import BOARD, added_part_refs

PREFIX = {
    "led": "D",
    "rgb-led": "D",
    "pushbutton": "SW",
    "potentiometer-10k": "RV",
    "buzzer": "BZ",
    "sg90-servo": "M",
    "relay-module-1ch": "K",
}


def _q(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def kicad_netlist(
    spec: ProjectSpec, board: BoardDef, alloc: Allocation, catalog: Catalog, nets: list[Net]
) -> str:
    """Construit le fichier .net."""
    refs: dict[str, str] = {BOARD: "J1"}
    pin_numbers: dict[str, dict[str, int]] = {}
    counters: dict[str, int] = {"J": 1}
    comps: list[str] = []

    board_labels = []
    for net in nets:
        for node in net.nodes:
            if node.ref == BOARD and node.pin not in board_labels:
                board_labels.append(node.pin)
    pin_numbers[BOARD] = {label: i + 1 for i, label in enumerate(board_labels)}
    n = max(len(board_labels), 2)
    comps.append(
        f"    (comp (ref {_q('J1')}) (value {_q(board.name)}) "
        f"(footprint {_q(f'Connector_PinSocket_2.54mm:PinSocket_1x{n:02d}_P2.54mm_Vertical')}) "
        f"(description {_q('Supports pour ' + board.name + ' : ' + ', '.join(board_labels))}))"
    )

    def next_ref(prefix: str) -> str:
        counters[prefix] = counters.get(prefix, 0) + 1
        return f"{prefix}{counters[prefix]}"

    for inst in spec.parts:
        comp = catalog.component(inst.component)
        if comp.passive or not comp.pins:
            continue
        ref = next_ref(PREFIX.get(comp.id, "U"))
        refs[inst.name] = ref
        pin_numbers[inst.name] = {p.name: i + 1 for i, p in enumerate(comp.pins)}
        footprint = comp.kicad.get("footprint", "")
        comps.append(
            f"    (comp (ref {_q(ref)}) (value {_q(comp.name)}) (footprint {_q(footprint)}) "
            f"(description {_q(inst.name)}))"
        )
    for rname, value in added_part_refs(alloc):
        ref = next_ref("R")
        refs[rname] = ref
        pin_numbers[rname] = {"1": 1, "2": 2}
        comps.append(
            f"    (comp (ref {_q(ref)}) (value {_q(value)}) "
            f"(footprint {_q('Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal')}) "
            f"(description {_q(rname)}))"
        )

    net_blocks: list[str] = []
    for code, net in enumerate(nets, 1):
        nodes = " ".join(
            f"(node (ref {_q(refs[node.ref])}) (pin {_q(str(pin_numbers[node.ref][node.pin]))}))"
            for node in net.nodes
            if node.ref in refs and node.pin in pin_numbers.get(node.ref, {})
        )
        net_blocks.append(f"    (net (code {_q(str(code))}) (name {_q(net.name)}) {nodes})")

    date = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    return "\n".join(
        [
            '(export (version "E")',
            f"  (design (source {_q(spec.title)}) (date {_q(date)}) (tool {_q('MicroForge')}))",
            "  (components",
            *comps,
            "  )",
            "  (nets",
            *net_blocks,
            "  )",
            ")",
            "",
        ]
    )
