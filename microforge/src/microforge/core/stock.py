"""Choix des résistances ajoutées automatiquement parmi les valeurs que l'utilisateur possède.

Le moteur calcule une valeur « idéale » (LED : 220 Ω en 5 V ; tirage 1-Wire : 4,7 kΩ ; pont 1 k/2 k).
Une valeur voisine convient presque toujours ; mieux vaut utiliser la résistance du tiroir que d'en
acheter une. Plages acceptées (choix conservateurs, documentés dans le guide) :

* **série de LED** : 0,68 × à 4,6 × la valeur idéale (courant de ≈ 15 mA à ≈ 2 mA, la LED reste visible) ;
* **tirage (pull-up)** : 0,47 × à 2,2 × (4,7 kΩ → 2,2 kΩ à 10 kΩ, plage d'usage du 1-Wire et de l'I2C) ;
* **pont diviseur 5 V → 3,3 V** : rapport bas/(haut+bas) entre 0,60 et 0,72 (3,0 V à 3,6 V en sortie),
  résistance haute entre 470 Ω et 10 kΩ.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from microforge.core.models import AddedPart
from microforge.core.values import format_value, parse_value

RANGES = {"series": (0.68, 4.6), "pullup": (0.47, 2.2)}
DIVIDER_RATIO = (0.60, 0.72)
DIVIDER_HIGH = (470.0, 10_000.0)


def _closest(ideal: float, owned: list[float], lo: float, hi: float) -> float | None:
    fits = [v for v in owned if ideal * lo <= v <= ideal * hi]
    return min(fits, key=lambda v: abs(math.log10(v / ideal))) if fits else None


def _divider(owned: list[float]) -> tuple[float, float] | None:
    best: tuple[float, float, float] | None = None
    for high in owned:
        if not DIVIDER_HIGH[0] <= high <= DIVIDER_HIGH[1]:
            continue
        for low in owned:
            ratio = low / (high + low)
            if DIVIDER_RATIO[0] <= ratio <= DIVIDER_RATIO[1]:
                gap = abs(ratio - 2 / 3)
                if best is None or gap < best[0]:
                    best = (gap, high, low)
    return (best[1], best[2]) if best else None


def adapt_resistors(added: list[AddedPart], owned_ohms: Iterable[float]) -> list[str]:
    """Remplace en place les valeurs par des valeurs possédées ; renvoie une note par changement."""
    owned = sorted({float(v) for v in owned_ohms if v and v > 0})
    if not owned:
        return []
    notes = []
    for part in added:
        if part.component != "resistor":
            continue
        ideal = parse_value(part.value)
        if ideal is None:
            continue
        if part.kind == "divider":
            pair = _divider(owned)
            if pair is None:
                continue
            high, low = pair
            before = f"{part.value} / {part.value_low}"
            part.value, part.value_low = format_value(high, "Ω"), format_value(low, "Ω")
            part.from_stock = True
            notes.append(
                f"{part.name} : pont {part.value} / {part.value_low} pris dans ton stock "
                f"(au lieu de {before}, sortie ≈ {5 * low / (high + low):.2f} V)"
            )
            continue
        lo, hi = RANGES.get(part.kind, (1.0, 1.0))
        chosen = _closest(ideal, owned, lo, hi)
        if chosen is None:
            continue
        part.from_stock = True
        if math.isclose(chosen, ideal):
            continue
        before = part.value
        part.value = format_value(chosen, "Ω")
        notes.append(f"{part.name} : {part.value} pris dans ton stock (valeur idéale {before})")
    return notes
