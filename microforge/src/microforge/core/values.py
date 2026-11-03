"""Valeurs des composants passifs : saisie libre, séries normalisées, code couleur des résistances.

* ``parse_value("4k7")`` = 4700 ; ``parse_value("0,1 µF")`` = 1e-7 ; ``parse_value("2u2")`` = 2,2e-6 ;
* ``format_value(4700, "Ω")`` = « 4,7 kΩ » ;
* séries E6 / E12 / E24 (CEI 60063) et valeur normalisée la plus proche ;
* code couleur CEI 60062 : ``colors_for(4700)`` = marron violet rouge or ; ``value_from_colors(...)``.
"""

from __future__ import annotations

import math
import re

E6 = (1.0, 1.5, 2.2, 3.3, 4.7, 6.8)
E12 = (1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2)
E24 = (1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0,
       3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1)  # fmt: skip
SERIES = {"E6": E6, "E12": E12, "E24": E24}

PREFIX = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6, "m": 1e-3,
          "": 1.0, "r": 1.0, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9}  # fmt: skip
SI_FORMAT = [(1e9, "G"), (1e6, "M"), (1e3, "k"), (1.0, ""), (1e-3, "m"), (1e-6, "µ"),
             (1e-9, "n"), (1e-12, "p")]  # fmt: skip
UNIT_WORDS = re.compile(r"(ohms?|Ω|ω|farads?|f|henrys?|h|v|volts?|w|watts?|a)$", re.IGNORECASE)

#: Code couleur (CEI 60062) : chiffre et multiplicateur.
COLORS = ["noir", "marron", "rouge", "orange", "jaune", "vert", "bleu", "violet", "gris", "blanc"]
MULTIPLIER = {**{c: 10.0**i for i, c in enumerate(COLORS)}, "or": 0.1, "argent": 0.01}
TOLERANCE = {"marron": 1.0, "rouge": 2.0, "vert": 0.5, "bleu": 0.25, "violet": 0.1, "or": 5.0,
             "argent": 10.0}  # fmt: skip


def parse_value(text: str | float | int | None) -> float | None:
    """Valeur numérique d'une saisie libre : « 4k7 », « 4,7 kΩ », « 100nF », « 2u2 », « 1R0 »…"""
    if text is None:
        return None
    if isinstance(text, int | float):
        return float(text)
    s = str(text).strip().replace(" ", "").replace(",", ".")
    s = UNIT_WORDS.sub("", s)
    if not s:
        return None
    # Notation « 4k7 » / « 2u2 » / « 1R0 » : le préfixe remplace la virgule.
    m = re.fullmatch(r"(\d+)([pnuµμmrRkKMG])(\d+)", s)
    if m:
        prefix = "r" if m.group(2) == "R" else m.group(2)
        return float(f"{m.group(1)}.{m.group(3)}") * PREFIX[prefix]
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([pnuµμmrRkKMG]?)", s)
    if not m:
        return None
    prefix = m.group(2)
    if prefix == "R":
        prefix = "r"
    return float(m.group(1)) * PREFIX[prefix]


def format_value(value: float, unit: str = "") -> str:
    """4700, « Ω » -> « 4,7 kΩ » ; 1e-7, « F » -> « 100 nF »."""
    if value == 0:
        return f"0 {unit}".strip()
    for factor, prefix in SI_FORMAT:
        if abs(value) >= factor * 0.999:
            return (f"{value / factor:.3g}".replace(".", ",") + f" {prefix}{unit}").strip()
    return f"{value:.3g} {unit}".strip()


def series_values(name: str, lo: float, hi: float) -> list[float]:
    """Toutes les valeurs d'une série entre ``lo`` et ``hi`` (bornes incluses)."""
    base = SERIES[name]
    out = []
    for exp in range(math.floor(math.log10(lo)) - 1, math.ceil(math.log10(hi)) + 1):
        for m in base:
            v = round(m * 10.0**exp, 12)
            if lo * 0.999 <= v <= hi * 1.001:
                out.append(v)
    return sorted(set(out))


def nearest(value: float, candidates: list[float]) -> float:
    """Valeur la plus proche en échelle logarithmique (ce qui compte pour un passif)."""
    return min(candidates, key=lambda c: abs(math.log10(c) - math.log10(value)))


def colors_for(ohms: float, bands: int = 4, tolerance: str = "or") -> list[str]:
    """Anneaux d'une résistance : 4 anneaux (2 chiffres) ou 5 anneaux (3 chiffres)."""
    digits = 2 if bands == 4 else 3
    if ohms <= 0:
        raise ValueError("valeur strictement positive attendue")
    exp = math.floor(math.log10(ohms)) - (digits - 1)
    mantissa = round(ohms / 10.0**exp)
    if mantissa >= 10**digits:  # 9,99 arrondi à 10,0
        mantissa //= 10
        exp += 1
    mult = next((c for c, m in MULTIPLIER.items() if math.isclose(m, 10.0**exp)), None)
    if mult is None:
        raise ValueError(f"{ohms} Ω hors de la plage du code couleur")
    return [COLORS[int(d)] for d in str(mantissa).zfill(digits)] + [mult, tolerance]


def value_from_colors(colors: list[str]) -> tuple[float, float | None]:
    """(valeur en Ω, tolérance en %) à partir des anneaux, lus depuis le côté opposé à l'anneau or."""
    names = [c.strip().lower() for c in colors]
    if len(names) not in (3, 4, 5):
        raise ValueError("3, 4 ou 5 anneaux attendus")
    digits_n = 3 if len(names) == 5 else 2
    try:
        digits = "".join(str(COLORS.index(c)) for c in names[:digits_n])
        mult = MULTIPLIER[names[digits_n]]
    except (ValueError, KeyError) as exc:
        raise ValueError(f"couleur inconnue dans {colors}") from exc
    tol = TOLERANCE.get(names[digits_n + 1]) if len(names) > digits_n + 1 else 20.0
    return round(int(digits) * mult, 6), tol
