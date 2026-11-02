"""Schéma de câblage en SVG (vue « blocs » : carte à gauche, composants à droite, un fil par liaison).

Accessible : ``role="img"``, ``<title>`` et ``<desc>`` décrivant les liaisons, texte réel (pas
d'image), couleurs doublées par des étiquettes.
"""

from __future__ import annotations

from html import escape

from microforge.core.allocator import Allocation
from microforge.core.catalog import Catalog
from microforge.core.models import BoardDef, ProjectSpec, SignalRole
from microforge.core.outputs.colors import wire_color

ROW = 24
BOARD_X, BOARD_W = 30, 230
COMP_X, COMP_W = 640, 240


def wiring_svg(spec: ProjectSpec, board: BoardDef, alloc: Allocation, catalog: Catalog) -> str:
    """Construit le SVG du câblage."""
    # Points de connexion côté carte (dans l'ordre : rails, masse, bus, signaux)
    rank = {SignalRole.POWER: 0, SignalRole.GROUND: 1}
    board_points: list[str] = []
    for a in sorted(
        alloc.assignments,
        key=lambda a: (
            rank.get(a.role, 2 if a.net.startswith(("I2C", "SPI")) else 3),
            a.board_label,
        ),
    ):
        if a.board_label not in board_points:
            board_points.append(a.board_label)
    board_y = {label: 70 + i * ROW for i, label in enumerate(board_points)}

    # Boîtes des composants
    comp_boxes: list[tuple[str, str, float, list[str]]] = []
    y = 50.0
    pin_y: dict[tuple[str, str], float] = {}
    for inst in spec.parts:
        comp = catalog.component(inst.component)
        pins = [a.pin for a in alloc.for_part(inst.name)]
        if not pins:
            continue
        comp_boxes.append((inst.name, comp.name, y, pins))
        for i, pin in enumerate(pins):
            pin_y[(inst.name, pin)] = y + 30 + i * ROW
        y += 30 + len(pins) * ROW + 26

    height = int(max(70 + len(board_points) * ROW + 40, y + 20))
    width = COMP_X + COMP_W + 30
    resist = {(p.part, p.pin): p for p in alloc.added_parts}

    out: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-labelledby="mf-title mf-desc" '
        'font-family="system-ui, sans-serif" font-size="13">',
        f'<title id="mf-title">Câblage : {escape(spec.title)}</title>',
        '<desc id="mf-desc">'
        + escape("; ".join(f"{a.part}.{a.pin} vers {a.board_label}" for a in alloc.assignments))
        + "</desc>",
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        # Carte
        f'<rect x="{BOARD_X}" y="40" width="{BOARD_W}" height="{len(board_points) * ROW + 40}" '
        'rx="10" fill="#0f3d2e" stroke="#0b2b20" stroke-width="2"/>',
        f'<text x="{BOARD_X + 12}" y="60" fill="#ffffff" font-weight="700">'
        f"{escape(board.name.split(' (')[0][:26])}</text>",
    ]
    for label, by in board_y.items():
        out.append(
            f'<circle cx="{BOARD_X + BOARD_W}" cy="{by}" r="5" fill="#e5e7eb" stroke="#111"/>'
            f'<text x="{BOARD_X + BOARD_W - 12}" y="{by + 4}" fill="#ffffff" text-anchor="end">'
            f"{escape(label)}</text>"
        )

    # Fils
    for i, a in enumerate(alloc.assignments):
        by = board_y[a.board_label]
        cy = pin_y.get((a.part, a.pin))
        if cy is None:
            continue
        if a.role == SignalRole.GROUND:
            _, hex_color, _ = wire_color("GND")
        elif a.role == SignalRole.POWER:
            hex_color = "#d62828" if board.rails.get(a.board_label, 5) > 4 else "#f77f00"
        else:
            _, hex_color, _ = wire_color(a.net)
        x1, x2 = BOARD_X + BOARD_W + 5, COMP_X - 5
        mid = x1 + 40 + (i % 14) * 22
        out.append(
            f'<polyline points="{x1},{by} {mid},{by} {mid},{cy} {x2},{cy}" fill="none" '
            f'stroke="{hex_color}" stroke-width="2.5" stroke-linejoin="round"/>'
        )
        r = resist.get((a.part, a.pin))
        if r is not None:
            rx = (mid + x2) / 2 - 26
            label = r.value + (f"/{r.value_low}" if r.value_low else "")
            out.append(
                f'<rect x="{rx}" y="{cy - 8}" width="52" height="16" fill="#fde68a" stroke="#92400e"/>'
                f'<text x="{rx + 26}" y="{cy + 4}" text-anchor="middle" font-size="10">{escape(label)}</text>'
            )

    # Composants
    for name, title, top, pins in comp_boxes:
        h = 30 + len(pins) * ROW
        out.append(
            f'<rect x="{COMP_X}" y="{top}" width="{COMP_W}" height="{h}" rx="8" '
            'fill="#eef2ff" stroke="#3730a3" stroke-width="1.5"/>'
            f'<text x="{COMP_X + 10}" y="{top + 18}" font-weight="700">{escape(name)}</text>'
            f'<text x="{COMP_X + COMP_W - 8}" y="{top + 18}" text-anchor="end" font-size="10" '
            f'fill="#4b5563">{escape(title[:34])}</text>'
        )
        for i, pin in enumerate(pins):
            py = top + 30 + i * ROW
            out.append(
                f'<circle cx="{COMP_X}" cy="{py}" r="5" fill="#e5e7eb" stroke="#111"/>'
                f'<text x="{COMP_X + 12}" y="{py + 4}">{escape(pin)}</text>'
            )
    out.append("</svg>")
    return "\n".join(out)
