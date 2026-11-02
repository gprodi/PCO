"""Tableau de câblage (Markdown accessible : en-têtes de colonnes, texte explicite, pas que la couleur)."""

from __future__ import annotations

from microforge.core.allocator import Allocation
from microforge.core.catalog import Catalog
from microforge.core.models import BoardDef, ProjectSpec, SignalRole
from microforge.core.outputs.colors import wire_color

_ROLE_FR = {
    SignalRole.POWER: "alimentation",
    SignalRole.GROUND: "masse",
    SignalRole.GPIO_IN: "entrée numérique",
    SignalRole.GPIO_OUT: "sortie numérique",
    SignalRole.GPIO_IO: "entrée/sortie",
    SignalRole.PWM: "sortie PWM",
    SignalRole.ADC: "entrée analogique",
    SignalRole.I2C_SDA: "I2C données (SDA)",
    SignalRole.I2C_SCL: "I2C horloge (SCL)",
    SignalRole.SPI_MOSI: "SPI MOSI",
    SignalRole.SPI_MISO: "SPI MISO",
    SignalRole.SPI_SCK: "SPI horloge",
    SignalRole.SPI_CS: "SPI sélection (CS)",
}


def wiring_table(spec: ProjectSpec, board: BoardDef, alloc: Allocation, catalog: Catalog) -> str:
    """Un fil par ligne, dans l'ordre de montage conseillé (masse, alimentation, bus, signaux)."""
    rank = {SignalRole.GROUND: 0, SignalRole.POWER: 1}
    rows = sorted(
        alloc.assignments,
        key=lambda a: (
            rank.get(a.role, 2 if a.net.startswith(("I2C", "SPI")) else 3),
            a.part,
            a.pin,
        ),
    )
    series = {(p.part, p.pin): p for p in alloc.added_parts if p.kind == "series"}
    divider = {(p.part, p.pin): p for p in alloc.added_parts if p.kind == "divider"}
    pullup = {(p.part, p.pin): p for p in alloc.added_parts if p.kind == "pullup"}

    lines = [
        f"## Câblage — {spec.title}",
        "",
        f"Carte : **{board.name}** (logique {board.logic_v:g} V). "
        "Couleurs conseillées : rouge = 5 V, orange = 3,3 V, noir = masse, bleu = SDA, "
        "jaune = SCL, violet = SPI, vert = signal.",
        "",
        "| # | Composant | Broche composant | Broche carte | Rôle | Fil | Remarque |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, a in enumerate(rows, 1):
        voltage = board.rails.get(a.board_label)
        if a.role == SignalRole.POWER:
            color = "rouge" if (voltage or 5) > 4 else "orange"
        elif a.role == SignalRole.GROUND:
            color = "noir"
        else:
            color = wire_color(a.net)[0]
        note = a.note
        key = (a.part, a.pin)
        if key in series:
            note = f"via résistance {series[key].value} en série. {note}".strip()
        if key in divider:
            d = divider[key]
            note = f"via pont diviseur {d.value} (côté capteur) / {d.value_low} (vers GND). {note}".strip()
        if key in pullup:
            note = f"+ pull-up {pullup[key].value} vers {pullup[key].rail}. {note}".strip()
        if a.i2c_address is not None:
            note = f"adresse I2C {hex(a.i2c_address)}. {note}".strip()
        comp = catalog.component(next(p.component for p in spec.parts if p.name == a.part))
        lines.append(
            f"| {i} | {a.part} ({comp.name}) | {a.pin} | {a.board_label} | "
            f"{_ROLE_FR.get(a.role, a.role.value)} | {color} | {note} |"
        )
    if alloc.added_parts:
        lines += ["", "### Composants ajoutés automatiquement", ""]
        for p in alloc.added_parts:
            low = f" + {p.value_low}" if p.value_low else ""
            lines.append(f"- `{p.name}` : {p.value}{low} — {p.reason}")
    return "\n".join(lines) + "\n"
