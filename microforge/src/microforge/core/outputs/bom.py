"""Nomenclature (BOM) et liste d'achat = BOM − inventaire."""

from __future__ import annotations

import csv
import io
from collections import Counter

from pydantic import BaseModel, Field

from microforge.core.allocator import Allocation
from microforge.core.catalog import Catalog
from microforge.core.models import BOMLine, ProjectSpec
from microforge.core.netlist import added_part_refs
from microforge.core.values import format_value

TOOLING = ["breadboard-830", "usb-cable"]


def dupont_estimate(spec: ProjectSpec, alloc: Allocation, catalog: Catalog) -> int:
    """Fils Dupont mâle-mâle pour un montage sur plaque d'essai : une liaison par broche de signal
    affectée, plus l'alimentation et la masse de chaque composant qui a des broches, plus 2 fils
    pour amener les rails de la carte à la plaque, plus une marge de 10 %."""
    powered = sum(1 for p in spec.parts if catalog.component(p.component).pins)
    resistors = len(alloc.added_parts)
    raw = len(alloc.assignments) + 2 * powered + 2 + resistors
    return max(4, round(raw * 1.1))


def build_bom(
    spec: ProjectSpec, alloc: Allocation, catalog: Catalog, tooling: bool = True
) -> list[BOMLine]:
    """Carte + composants + résistances ajoutées + outillage de prototypage."""
    board = catalog.board(spec.board)
    lines: list[BOMLine] = [
        BOMLine(component=board.id, name=board.name, quantity=1, unit_price_eur=board.price_eur)
    ]
    counts = Counter(catalog.component(p.component).id for p in spec.parts)
    for cid, qty in counts.items():
        comp = catalog.component(cid)
        lines.append(
            BOMLine(component=cid, name=comp.name, quantity=qty, unit_price_eur=comp.price_eur)
        )
    for extra in spec.bom_extra:
        comp = catalog.component(extra.component)
        unit = comp.parametric.unit if comp.parametric else ""
        label = f"{comp.name} {format_value(extra.value, unit)}" if extra.value else comp.name
        lines.append(
            BOMLine(
                component=comp.id,
                name=label,
                quantity=extra.quantity,
                unit_price_eur=comp.price_eur,
                note=extra.note or "hors carte (voir le guide)",
            )
        )
    values = Counter(value for _, value in added_part_refs(alloc))
    stocked = {p.value for p in alloc.added_parts if p.from_stock} | {
        p.value_low for p in alloc.added_parts if p.from_stock and p.value_low
    }
    for value, qty in sorted(values.items()):
        lines.append(
            BOMLine(
                component="resistor",
                name=f"Résistance {value} 1/4 W",
                quantity=qty,
                unit_price_eur=catalog.component("resistor").price_eur,
                note=f"{value} — dans ton stock" if value in stocked else value,
            )
        )
    if tooling:
        if "dupont-wire-mm" not in counts:
            lines.append(
                BOMLine(
                    component="dupont-wire-mm",
                    name=catalog.component("dupont-wire-mm").name,
                    quantity=dupont_estimate(spec, alloc, catalog),
                    unit_price_eur=catalog.component("dupont-wire-mm").price_eur,
                    note="estimation : une liaison par fil sur plaque d'essai (+10 %)",
                )
            )
        for tid in TOOLING:
            if tid not in counts:
                comp = catalog.component(tid)
                lines.append(
                    BOMLine(
                        component=tid,
                        name=comp.name,
                        quantity=1,
                        unit_price_eur=comp.price_eur,
                        note="prototypage",
                    )
                )
    return lines


class Offer(BaseModel):
    """Offre fournisseur (issue du pipeline E1 : API, scraping…)."""

    supplier: str
    component: str
    unit_price_eur: float
    url: str = ""
    stock: int | None = None


class ShoppingLine(BaseModel):
    component: str
    name: str
    needed: int
    owned: int
    to_buy: int
    unit_price_eur: float | None = None
    supplier: str = "prix indicatif catalogue"
    url: str = ""

    @property
    def subtotal(self) -> float:
        return round((self.unit_price_eur or 0) * self.to_buy, 2)


class ShoppingList(BaseModel):
    lines: list[ShoppingLine] = Field(default_factory=list)

    @property
    def total_eur(self) -> float:
        return round(sum(line.subtotal for line in self.lines if line.to_buy > 0), 2)

    @property
    def to_buy(self) -> list[ShoppingLine]:
        return [line for line in self.lines if line.to_buy > 0]

    def by_supplier(self) -> dict[str, list[ShoppingLine]]:
        groups: dict[str, list[ShoppingLine]] = {}
        for line in self.to_buy:
            groups.setdefault(line.supplier, []).append(line)
        return groups

    def to_csv(self) -> str:
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(
            [
                "composant",
                "désignation",
                "besoin",
                "possédé",
                "à acheter",
                "prix unitaire €",
                "sous-total €",
                "fournisseur",
                "lien",
            ]
        )
        for line in self.lines:
            w.writerow(
                [
                    line.component,
                    line.name,
                    line.needed,
                    line.owned,
                    line.to_buy,
                    line.unit_price_eur if line.unit_price_eur is not None else "",
                    line.subtotal,
                    line.supplier,
                    line.url,
                ]
            )
        return buf.getvalue()

    def to_markdown(self) -> str:
        if not self.to_buy:
            return "Tu as déjà tout le nécessaire 🎉\n"
        out = [
            "| Désignation | Qté | Prix unitaire | Sous-total | Fournisseur |",
            "|---|---|---|---|---|",
        ]
        for line in self.to_buy:
            price = f"{line.unit_price_eur:.2f} €" if line.unit_price_eur is not None else "?"
            supplier = f"[{line.supplier}]({line.url})" if line.url else line.supplier
            out.append(
                f"| {line.name} | {line.to_buy} | {price} | {line.subtotal:.2f} € | {supplier} |"
            )
        out.append(f"\n**Total estimé : {self.total_eur:.2f} €** (hors frais de port)")
        return "\n".join(out) + "\n"


def shopping_list(
    bom: list[BOMLine], inventory: dict[str, int], offers: list[Offer] | None = None
) -> ShoppingList:
    """Calcule ce qu'il manque et choisit l'offre la moins chère quand le pipeline E1 en fournit."""
    best: dict[str, Offer] = {}
    for offer in offers or []:
        if offer.stock == 0:
            continue
        current = best.get(offer.component)
        if current is None or offer.unit_price_eur < current.unit_price_eur:
            best[offer.component] = offer
    remaining = dict(inventory)
    result = ShoppingList()
    for line in bom:
        owned = min(remaining.get(line.component, 0), line.quantity)
        remaining[line.component] = remaining.get(line.component, 0) - owned
        offer = best.get(line.component)
        result.lines.append(
            ShoppingLine(
                component=line.component,
                name=line.name,
                needed=line.quantity,
                owned=owned,
                to_buy=line.quantity - owned,
                unit_price_eur=offer.unit_price_eur if offer else line.unit_price_eur,
                supplier=offer.supplier if offer else "prix indicatif catalogue",
                url=offer.url if offer else "",
            )
        )
    return result
