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

TOOLING = ["breadboard-830", "jumper-wires", "usb-cable"]


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
    values = Counter(value for _, value in added_part_refs(alloc))
    for value, qty in sorted(values.items()):
        lines.append(
            BOMLine(
                component="resistor",
                name=f"Résistance {value} 1/4 W",
                quantity=qty,
                unit_price_eur=catalog.component("resistor").price_eur,
                note=value,
            )
        )
    if tooling:
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
