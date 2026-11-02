"""Génération du firmware Arduino (C++) à partir de l'allocation.

Structure produite (compatible Arduino IDE, arduino-cli, PlatformIO et Wokwi) ::

    <projet>/
      <projet>.ino        setup() / loop() + logique du projet (lisible, à modifier)
      mf_components.h     broches, objets et fonctions des composants (généré)
      secrets.h           identifiants Wi-Fi (si besoin, à ne pas versionner)

Les fragments de code viennent du catalogue (``code:`` de chaque composant) : le code de base est
donc déterministe et compilable. Seule la *logique* (corps de ``loop``) peut venir d'un LLM.
"""

from __future__ import annotations

import re
from string import Template

from microforge.core.allocator import Allocation
from microforge.core.catalog import Catalog
from microforge.core.models import BUS_ROLES, BoardDef, ProjectSpec, SignalRole

WIFI_HELPERS = """
// ---- Wi-Fi ----
#include <WiFi.h>
#include "secrets.h"

inline bool mf_wifi_connect(unsigned long timeout_ms = 15000) {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < timeout_ms) { delay(250); }
  return WiFi.status() == WL_CONNECTED;
}

#if defined(ESP32)
#include <time.h>
// Heure locale via NTP (fuseau Europe/Paris par défaut ; Réunion : "<+04>-4").
inline void mf_time_begin(const char* tz = "CET-1CEST,M3.5.0,M10.5.0/3") {
  configTzTime(tz, "pool.ntp.org", "time.google.com");
}
inline String mf_time_hhmm() {
  struct tm t;
  if (!getLocalTime(&t, 2000)) { return "--:--"; }
  char buf[6]; strftime(buf, sizeof(buf), "%H:%M", &t);
  return String(buf);
}
#endif
"""

SECRETS_H = """// secrets.h — identifiants Wi-Fi. NE PAS VERSIONNER ce fichier avec de vraies valeurs.
#pragma once
#define WIFI_SSID "mon_wifi"
#define WIFI_PASSWORD "mon_mot_de_passe"
"""


def placeholder(pin_name: str) -> str:
    """Nom de placeholder d'une broche : « 1 » -> P1, « V+ » -> V_, « 3.3V » -> P3_3V."""
    key = re.sub(r"[^A-Za-z0-9]", "_", pin_name)
    return f"P{key}" if key[:1].isdigit() else key


def sketch_name(title: str) -> str:
    """Nom de dossier/sketch Arduino valide à partir du titre."""
    import unicodedata

    s = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return (s or "projet")[:40]


def _pin_constant(part: str, pin: str) -> str:
    return f"PIN_{part.upper()}_{re.sub(r'[^A-Za-z0-9]', '_', pin).upper()}".replace("__", "_")


def _pin_value(board: BoardDef, gpio: int, label: str) -> str:
    # Sur AVR, A0…A15 sont plus lisibles que 14…69 ; ailleurs on garde le numéro de GPIO.
    if board.family == "avr" and label.startswith("A") and label[1:].isdigit():
        return label
    return str(gpio)


class FirmwareGenerator:
    """Assemble mf_components.h + <projet>.ino."""

    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog

    def libraries(self, spec: ProjectSpec) -> list[str]:
        board = self.catalog.board(spec.board)
        libs: list[str] = []
        for inst in spec.parts:
            for lib in self.catalog.component(inst.component).code_for(board.family).libraries:
                if lib not in libs:
                    libs.append(lib)
        return libs

    def generate(self, spec: ProjectSpec, alloc: Allocation) -> dict[str, str]:
        """Renvoie {nom_de_fichier: contenu}."""
        board = self.catalog.board(spec.board)
        name = sketch_name(spec.title)
        includes: list[str] = []
        constants: list[str] = []
        globals_: list[str] = []
        apis: list[str] = []
        setup_once: list[str] = []
        setups: list[str] = []
        bus_constants: dict[str, str] = {}

        for inst in spec.parts:
            comp = self.catalog.component(inst.component)
            if comp.passive:
                continue
            tpl = comp.code_for(board.family)
            mapping: dict[str, str] = {"name": inst.name}
            for a in alloc.for_part(inst.name):
                if a.gpio is None:
                    continue
                if a.role in BUS_ROLES:
                    const = f"PIN_{a.net}"
                    bus_constants[const] = (
                        f"const uint8_t {const} = {_pin_value(board, a.gpio, a.board_label)};"
                        f"  // {a.board_label} (bus partagé)"
                    )
                else:
                    const = _pin_constant(inst.name, a.pin)
                    constants.append(
                        f"const uint8_t {const} = {_pin_value(board, a.gpio, a.board_label)};"
                        f"  // {a.board_label} -> {inst.name}.{a.pin}"
                    )
                mapping[placeholder(a.pin)] = const
                if a.i2c_address is not None:
                    mapping["I2C_ADDR"] = f"0x{a.i2c_address:02X}"
            if "I2C_ADDR" not in mapping and comp.i2c_addresses:
                mapping["I2C_ADDR"] = f"0x{comp.i2c_addresses[0]:02X}"

            def render(text: str, inst_name: str = inst.name, m: dict[str, str] = mapping) -> str:
                try:
                    return Template(text).substitute(m)
                except KeyError as exc:  # placeholder sans broche affectée
                    raise ValueError(
                        f"Code de {inst_name} : placeholder {exc} sans broche affectée"
                    ) from exc

            for inc in tpl.includes:
                if inc not in includes:
                    includes.append(inc)
            for line in tpl.setup_once:
                if line not in setup_once:
                    setup_once.append(line)
            header = f"// --- {inst.name} : {comp.name}"
            if tpl.globals.strip():
                globals_.append(f"{header}\n{render(tpl.globals).rstrip()}")
            if tpl.api.strip():
                apis.append(f"{header}\n{render(tpl.api).rstrip()}")
            if tpl.setup.strip():
                body = "\n".join(f"  {ln}" for ln in render(tpl.setup).strip().splitlines())
                setups.append(f"  // {inst.name}\n{body}")

        header_lines = [
            f"// mf_components.h — généré par MicroForge pour « {spec.title} »",
            f"// Carte : {board.name} — FQBN {board.fqbn}",
            "// Ne modifiez pas ce fichier à la main : régénérez-le depuis MicroForge.",
            "// À inclure UNIQUEMENT depuis le .ino (les fonctions y sont définies).",
            "#pragma once",
            "#include <Arduino.h>",
            *includes,
            "",
            "#if defined(ESP32)",
            "  #define MF_ADC_MAX 4095",
            "#else",
            "  #define MF_ADC_MAX 1023",
            "#endif",
            "",
            "// ---- Broches (cf. tableau de câblage) ----",
            *bus_constants.values(),
            *constants,
            "",
            "// ---- Objets des composants ----",
            *globals_,
            "",
            "// ---- Fonctions des composants (utilisables dans loop()) ----",
            *apis,
        ]
        if spec.uses_wifi:
            header_lines.append(WIFI_HELPERS)
        header_lines += [
            "",
            "// ---- Initialisation de tous les composants ----",
            "inline void mf_setup_components() {",
            *(f"  {ln}" for ln in setup_once),
            *setups,
            "}",
            "",
        ]

        wifi_setup = ""
        if spec.uses_wifi:
            wifi_setup = (
                '  Serial.println(mf_wifi_connect() ? F("Wi-Fi connecté") : F("Wi-Fi : échec"));\n'
            )
            if board.family == "esp32" and "mf_time" in spec.logic + spec.setup_extra:
                wifi_setup += "  mf_time_begin();\n"
        logic = "\n".join(f"  {ln}" if ln.strip() else "" for ln in spec.logic.strip().splitlines())
        setup_extra = "\n".join(f"  {ln}" for ln in spec.setup_extra.strip().splitlines())
        ino = "\n".join(
            [
                f"// {spec.title} — généré par MicroForge",
                *(f"// {ln}" for ln in (spec.description or "").splitlines() if ln.strip()),
                f"// Carte : {board.name}",
                '#include "mf_components.h"',
                "",
                spec.globals_extra.strip(),
                "",
                "void setup() {",
                "  Serial.begin(115200);",
                "  mf_setup_components();",
                wifi_setup.rstrip("\n"),
                setup_extra,
                "}",
                "",
                "void loop() {",
                logic or "  delay(1000);",
                "}",
                "",
            ]
        )
        ino = re.sub(r"\n{3,}", "\n\n", ino)
        files = {f"{name}/{name}.ino": ino, f"{name}/mf_components.h": "\n".join(header_lines)}
        if spec.uses_wifi:
            files[f"{name}/secrets.h"] = SECRETS_H
        return files


def is_signal(role: SignalRole) -> bool:
    return role not in (SignalRole.POWER, SignalRole.GROUND, SignalRole.NC)
