"""Construction de la netlist (liste des équipotentielles) à partir de l'allocation.

Une *net* relie des broches au même potentiel. Les protections ajoutées (résistance série, pont
diviseur, pull-up) découpent ou complètent les nets :

* série     : ``GPIO -> R.1`` | ``R.2 -> LED.A``
* diviseur  : ``ECHO -> Rh.1`` | ``Rh.2 + Rb.1 -> GPIO`` | ``Rb.2 -> GND``
* pull-up   : ``R.1`` sur la net du signal, ``R.2`` sur le rail
"""

from __future__ import annotations

from collections import OrderedDict

from microforge.core.allocator import Allocation
from microforge.core.models import BoardDef, Net, NetNode, SignalRole

BOARD = "board"


def build_nets(board: BoardDef, alloc: Allocation) -> list[Net]:
    """Construit la liste ordonnée des nets."""
    nets: OrderedDict[str, Net] = OrderedDict()

    def add(net: str, ref: str, pin: str, kind: str = "signal") -> None:
        if net not in nets:
            nets[net] = Net(name=net, nodes=[], kind=kind)
        node = NetNode(ref=ref, pin=pin)
        if node not in nets[net].nodes:
            nets[net].nodes.append(node)

    series = {(p.part, p.pin): p for p in alloc.added_parts if p.kind == "series"}
    divider = {(p.part, p.pin): p for p in alloc.added_parts if p.kind == "divider"}
    pullup = {(p.part, p.pin): p for p in alloc.added_parts if p.kind == "pullup"}

    for a in alloc.assignments:
        if a.role == SignalRole.POWER:
            add(a.net, BOARD, a.board_label, "power")
            add(a.net, a.part, a.pin, "power")
            continue
        if a.role == SignalRole.GROUND:
            add("GND", BOARD, "GND", "ground")
            add("GND", a.part, a.pin, "ground")
            continue
        kind = "bus" if a.net.startswith(("I2C_", "SPI_")) else "signal"
        key = (a.part, a.pin)
        if key in series:
            r = series[key]
            add(a.net, BOARD, a.board_label, kind)
            add(a.net, r.name, "1", kind)
            add(f"{a.net}_R", r.name, "2", kind)
            add(f"{a.net}_R", a.part, a.pin, kind)
        elif key in divider:
            r = divider[key]
            low = f"{r.name}_bas"
            add(f"{a.net}_5V", a.part, a.pin, kind)
            add(f"{a.net}_5V", r.name, "1", kind)
            add(a.net, r.name, "2", kind)
            add(a.net, low, "1", kind)
            add(a.net, BOARD, a.board_label, kind)
            add("GND", BOARD, "GND", "ground")
            add("GND", low, "2", "ground")
        else:
            add(a.net, BOARD, a.board_label, kind)
            add(a.net, a.part, a.pin, kind)
        if key in pullup:
            r = pullup[key]
            add(a.net, r.name, "1", kind)
            rail_net = (r.rail or "3V3").replace(".", "_").upper()
            rail_net = next(
                (
                    x.net
                    for x in alloc.assignments
                    if x.role == SignalRole.POWER and x.board_label == r.rail
                ),
                rail_net,
            )
            add(rail_net, r.name, "2", "power")

    # Ordre lisible : alimentation, masse, bus, signaux
    rank = {"power": 0, "ground": 1, "bus": 2, "signal": 3}
    return sorted(nets.values(), key=lambda n: (rank.get(n.kind, 9), n.name))


def added_part_refs(alloc: Allocation) -> list[tuple[str, str]]:
    """(nom, valeur) de chaque résistance ajoutée, y compris le bas des ponts diviseurs."""
    refs: list[tuple[str, str]] = []
    for p in alloc.added_parts:
        refs.append((p.name, p.value))
        if p.kind == "divider" and p.value_low:
            refs.append((f"{p.name}_bas", p.value_low))
    return refs
