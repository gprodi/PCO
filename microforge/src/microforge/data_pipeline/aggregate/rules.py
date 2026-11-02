"""Règles d'homogénéisation et de détection des entrées corrompues (C3).

Toutes les fonctions sont pures et testées unitairement (tests/test_pipeline.py).
"""

from __future__ import annotations

import html
import re
import unicodedata
from datetime import UTC, datetime

# ------------------------------------------------------------------ textes
_TAGS = re.compile(r"<[^>]+>")


def clean_text(value: str | None) -> str | None:
    """Supprime les balises HTML, décode les entités, normalise les espaces et l'Unicode."""
    if value is None:
        return None
    text = html.unescape(_TAGS.sub(" ", str(value)))
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def normalize_mpn(mpn: str | None) -> str | None:
    """Numéro de pièce fabricant : majuscules, sans espaces ni suffixes d'emballage courants."""
    if not mpn:
        return None
    m = re.sub(r"\s+", "", mpn.upper())
    m = re.sub(r"(-?TR|/TR|-REEL|#PBF)$", "", m)
    return m or None


_MANUFACTURERS = {
    "espressif": "Espressif",
    "aosong": "Aosong",
    "asair": "Aosong",
    "bosch": "Bosch Sensortec",
    "tdk invensense": "TDK InvenSense",
    "invensense": "TDK InvenSense",
    "maxim": "Analog Devices / Maxim",
    "analog devices": "Analog Devices / Maxim",
    "adafruit": "Adafruit",
    "dfrobot": "DFRobot",
    "seeed": "Seeed Studio",
    "raspberry pi": "Raspberry Pi",
    "arduino": "Arduino",
    "microchip": "Microchip",
    "worldsemi": "Worldsemi",
    "texas instruments": "Texas Instruments",
    "stmicroelectronics": "STMicroelectronics",
}


def normalize_manufacturer(name: str | None) -> str | None:
    """« ESPRESSIF SYSTEMS (SHANGHAI) CO., LTD. » -> « Espressif »."""
    text = clean_text(name)
    if not text:
        return None
    low = text.lower()
    for key, canonical in _MANUFACTURERS.items():
        if key in low:
            return canonical
    text = re.sub(
        r"\(.*?\)|,?\s*(co\.?,?\s*)?(ltd\.?|inc\.?|gmbh|corp\.?|llc)\b\.?", "", text, flags=re.I
    )
    return text.strip(" .,") or None


# ------------------------------------------------------------------ nombres / unités
_NUM = r"(\d+(?:[.,]\d+)?)"


def parse_number(text: str | float | int | None) -> float | None:
    """« 1 234,50 » -> 1234.5 ; « 3.50 € » -> 3.5 ; None si absent."""
    if text is None:
        return None
    if isinstance(text, int | float):
        return float(text)
    s = str(text).replace(" ", " ").replace(" ", " ")
    m = re.search(r"\d[\d\s.,]*", s)
    if not m:
        return None
    num = m.group(0).strip().replace(" ", "")
    if "," in num and "." in num:  # 1.234,50 (FR/DE) ou 1,234.50 (EN)
        num = (
            num.replace(".", "").replace(",", ".")
            if num.rfind(",") > num.rfind(".")
            else num.replace(",", "")
        )
    elif "," in num:
        num = num.replace(",", ".")
    try:
        return float(num)
    except ValueError:
        return None


def parse_stock(value: str | int | None) -> int | None:
    """« 12 345 In Stock » / « En stock (25) » -> int ; « Rupture » -> 0."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    low = str(value).lower()
    if any(w in low for w in ("rupture", "épuisé", "out of stock", "indisponible")):
        return 0
    n = parse_number(str(value).replace(".", "").replace(",", ""))
    return int(n) if n is not None else None


def parse_voltage_range(text: str | None) -> tuple[float, float] | None:
    """« 3V3 », « 3.3V », « 3,3 V », « 2.7V ~ 5.5V », « 3.3-5V », « 5 VDC » -> (min, max) en volts."""
    if not text:
        return None
    s = str(text).lower().replace(",", ".")
    s = re.sub(r"(\d)v(\d)", r"\1.\2", s)  # 3v3 -> 3.3
    s = s.replace("vdc", "v").replace("mv", "e-3v")
    values: list[float] = []
    for num, exp in re.findall(r"(\d+(?:\.\d+)?)(e-3)?\s*v?", s):
        v = float(num) * (1e-3 if exp else 1)
        if 0 < v <= 60:
            values.append(v)
    if not values:
        return None
    return (min(values), max(values))


def to_eur(
    amount: float | None, currency: str | None, eur_per_unit: dict[str, float]
) -> float | None:
    """Convertit en euros au taux BCE du jour de collecte (Frankfurter)."""
    if amount is None:
        return None
    cur = (currency or "EUR").upper().replace("€", "EUR").replace("$", "USD")
    rate = eur_per_unit.get(cur)
    return round(amount * rate, 4) if rate else None


# ------------------------------------------------------------------ vocabulaires contrôlés
_INTERFACES = {
    "I2C": ["i2c", "i²c", "iic", "twi"],
    "SPI": ["spi"],
    "UART": ["uart", "serial", "ttl", "rs232"],
    "1-Wire": ["1-wire", "onewire", "one-wire", "single bus", "single-bus"],
    "PWM": ["pwm"],
    "ADC": ["analog", "analogique", "adc"],
    "GPIO": ["digital", "numérique", "gpio"],
}


def normalize_interfaces(text: str | None) -> str:
    """Texte libre -> « I2C,SPI » (ordre stable, sans doublon)."""
    if not text:
        return ""
    low = str(text).lower()
    return ",".join(k for k, words in _INTERFACES.items() if any(w in low for w in words))


_PACKAGES = [
    (r"\bdip-?(\d+)", "DIP-{0}"),
    (r"\bsot-?23(-\d)?", "SOT-23{0}"),
    (r"\bto-?92", "TO-92"),
    (r"\bto-?220", "TO-220"),
    (r"\bsoic-?(\d+)", "SOIC-{0}"),
    (r"\blga-?(\d+)", "LGA-{0}"),
    (r"\bqfn-?(\d+)", "QFN-{0}"),
    (r"\b(module|plugin|through hole|tht)\b", "MODULE"),
]


def normalize_package(text: str | None) -> str | None:
    if not text:
        return None
    low = str(text).lower()
    for pattern, fmt in _PACKAGES:
        m = re.search(pattern, low)
        if m:
            groups = [g or "" for g in m.groups()] or [""]
            return fmt.format(*groups).upper() if "{0}" in fmt else fmt
    return clean_text(text)


def normalize_date(value: str | None) -> str | None:
    """Dates hétérogènes -> ISO 8601 UTC."""
    if not value:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%Y-%m-%dT%H:%M:%SZ",
    ):
        try:
            dt = datetime.strptime(value.replace("+00:00", "+0000") if "%z" in fmt else value, fmt)
            return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).isoformat()
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(value)
        return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).isoformat()
    except ValueError:
        return None
