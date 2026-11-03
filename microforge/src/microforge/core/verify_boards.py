"""Vérifie les bus par défaut des cartes du catalogue contre les fichiers officiels des cœurs Arduino.

Le moteur écrit ``Wire.begin()`` / ``SPI.begin()`` sans arguments : le firmware utilise donc les broches
définies par le cœur (``variants/<variante>/pins_arduino.h``). Si ``default_i2c`` / ``default_spi`` du
YAML diffèrent, le câblage dessiné ne correspond pas au code compilé. Cette vérification :

1. lit ``boards.txt`` du cœur pour trouver la variante de la carte (``<carte>.build.variant``) ;
2. télécharge ``variants/<variante>/pins_arduino.h`` (ou ``variant.h``) depuis le dépôt officiel ;
3. résout ``SDA``, ``SCL``, ``MOSI``, ``MISO``, ``SCK``, ``SS`` (y compris via ``PIN_WIRE_SDA``…) ;
4. compare avec le catalogue et liste les écarts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from microforge.core.catalog import Catalog, get_catalog
from microforge.core.models import BoardDef

RAW = "https://raw.githubusercontent.com/"
#: Dépôt officiel et branche de chaque cœur (préfixe du FQBN).
CORES = {
    "esp32:esp32": "espressif/arduino-esp32/master",
    "arduino:avr": "arduino/ArduinoCore-avr/master",
    "rp2040:rp2040": "earlephilhower/arduino-pico/master",
    "arduino:megaavr": "arduino/ArduinoCore-megaavr/master",
    "arduino:samd": "arduino/ArduinoCore-samd/master",
    "arduino:renesas_uno": "arduino/ArduinoCore-renesas/main",
    "esp8266:esp8266": "esp8266/Arduino/master",
}
ROLES = {
    "sda": ("SDA", "PIN_WIRE_SDA", "PIN_WIRE0_SDA"),
    "scl": ("SCL", "PIN_WIRE_SCL", "PIN_WIRE0_SCL"),
    "mosi": ("MOSI", "PIN_SPI_MOSI", "PIN_SPI0_MOSI"),
    "miso": ("MISO", "PIN_SPI_MISO", "PIN_SPI0_MISO"),
    "sck": ("SCK", "PIN_SPI_SCK", "PIN_SPI0_SCK"),
    "cs": ("SS", "PIN_SPI_SS", "PIN_SPI0_SS"),
}
#: Broches passées explicitement par le firmware généré (``codegen._bus_begin``) : un écart avec le
#: cœur y est volontaire (ESP32-CAM : I2C sur 14/15). Le CS est toujours passé aux pilotes.
EXPLICIT = {
    "esp32": {"sda", "scl", "mosi", "miso", "sck", "cs"},
    "esp8266": {"sda", "scl", "cs"},
    "rp2040": {"sda", "scl", "mosi", "miso", "sck", "cs"},
}
_INCLUDE = re.compile(r'^\s*#include\s+"([^"]+)"', re.M)
_DEFINE = re.compile(r"^\s*#define\s+(\w+)\s+\(?\s*([\w]+?)u?\s*\)?\s*(?://.*)?$", re.M)
_CONST = re.compile(
    r"static\s+const\s+(?:uint8_t|int|pin_size_t)\s+(\w+)\s*=\s*\(?\s*(\w+?)u?\s*\)?\s*;"
)


def parse_pins(header: str) -> dict[str, int]:
    """``#define`` et ``static const`` -> {nom: numéro}, en résolvant les alias (SDA = PIN_WIRE_SDA)."""
    raw: dict[str, str] = {}
    for name, value in _DEFINE.findall(header):
        raw.setdefault(name, value)
    for name, value in _CONST.findall(header):
        raw[name] = value
    out: dict[str, int] = {}

    def resolve(name: str, depth: int = 0) -> int | None:
        value = raw.get(name)
        if value is None or depth > 6:
            return None
        if value.isdigit():
            return int(value)
        return resolve(value, depth + 1)

    for name in raw:
        num = resolve(name)
        if num is not None:
            out[name] = num
    return out


def board_variant(boards_txt: str, board_id: str) -> str | None:
    m = re.search(rf"^{re.escape(board_id)}\.build\.variant=(\S+)", boards_txt, re.M)
    return m.group(1) if m else None


@dataclass
class BoardCheck:
    board: str
    status: str  # ok | ecart | non_verifie
    variant: str | None = None
    official: dict[str, int] = field(default_factory=dict)
    mismatches: dict[str, tuple[int, int]] = field(
        default_factory=dict
    )  # rôle: (catalogue, officiel)
    explicit: dict[str, tuple[int, int]] = field(
        default_factory=dict
    )  # écarts voulus, pins explicites
    message: str = ""


class BoardVerifier:
    def __init__(self, http: httpx.Client | None = None, catalog: Catalog | None = None) -> None:
        self.http = http or httpx.Client(timeout=30, follow_redirects=True)
        self.catalog = catalog or get_catalog()
        self._cache: dict[str, str | None] = {}

    def _get(self, path: str) -> str | None:
        if path not in self._cache:
            resp = self.http.get(RAW + path)
            self._cache[path] = resp.text if resp.status_code == 200 else None
        return self._cache[path]

    def check(self, board: BoardDef) -> BoardCheck:
        parts = board.fqbn.split(":")
        repo = CORES.get(":".join(parts[:2]))
        if not repo or len(parts) < 3:
            return BoardCheck(
                board.id, "non_verifie", message="cœur sans fichiers de variantes publics"
            )
        boards_txt = self._get(f"{repo}/boards.txt")
        variant = board_variant(boards_txt or "", parts[2])
        if not variant:
            return BoardCheck(board.id, "non_verifie", message=f"{parts[2]} absent de boards.txt")
        base = f"{repo}/variants/{variant}"
        header = self._with_includes(base, "pins_arduino.h") or self._with_includes(
            base, "variant.h"
        )
        if not header:
            return BoardCheck(
                board.id, "non_verifie", variant, message="fichier de variante introuvable"
            )
        pins = parse_pins(header)
        official = {
            role: next((pins[n] for n in names if n in pins), None) for role, names in ROLES.items()
        }
        official = {k: v for k, v in official.items() if v is not None}
        ours = {**board.default_i2c, **board.default_spi}
        differ = {
            role: (ours[role], value)
            for role, value in official.items()
            if role in ours and ours[role] != value
        }
        explicit_roles = EXPLICIT.get(board.family, {"cs"})
        mismatches = {r: v for r, v in differ.items() if r not in explicit_roles}
        explicit = {r: v for r, v in differ.items() if r in explicit_roles}
        if not official:
            return BoardCheck(
                board.id, "non_verifie", variant, message="aucune broche de bus trouvée"
            )
        return BoardCheck(
            board.id, "ecart" if mismatches else "ok", variant, official, mismatches, explicit
        )

    def _with_includes(self, base: str, name: str, depth: int = 0) -> str | None:
        """Texte du fichier + des fichiers qu'il inclut entre guillemets (chemins relatifs)."""
        text = self._get(f"{base}/{name}")
        if text is None or depth > 2:
            return text
        parts = [text]
        for inc in _INCLUDE.findall(text):
            path = f"{base}/{inc}"
            folder, _, file = path.rpartition("/")
            # normalise « variants/eightanaloginputs/../standard »
            segs: list[str] = []
            for seg in folder.split("/"):
                if seg == "..":
                    segs.pop()
                elif seg not in ("", "."):
                    segs.append(seg)
            included = self._with_includes("/".join(segs), file, depth + 1)
            if included:
                parts.append(included)
        return "\n".join(parts)

    def run(self) -> list[BoardCheck]:
        return [self.check(b) for b in self.catalog.boards.values()]


def report(checks: list[BoardCheck]) -> dict[str, Any]:
    return {
        "verifiees": sum(c.status != "non_verifie" for c in checks),
        "ok": sum(c.status == "ok" for c in checks),
        "ecarts": {
            c.board: {r: {"catalogue": a, "officiel": b} for r, (a, b) in c.mismatches.items()}
            for c in checks
            if c.status == "ecart"
        },
        "explicites": {
            c.board: {r: {"catalogue": a, "officiel": b} for r, (a, b) in c.explicit.items()}
            for c in checks
            if c.explicit
        },
        "non_verifiees": {c.board: c.message for c in checks if c.status == "non_verifie"},
    }
