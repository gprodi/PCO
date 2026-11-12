"""Mode apprentissage (onglet « Apprendre ») : montage pas à pas, avec le pourquoi de chaque fil,
programme expliqué ligne par ligne, notions du projet avec leur définition, quiz de l'étape.

Tout est déduit du projet réellement généré (affectations du moteur, capacités des broches de la
carte, résistances ajoutées, firmware) et de trois fichiers de données relus par des tests :
``api_doc.yaml``, ``glossaire.yaml``, ``quiz.yaml``.
"""

from __future__ import annotations

import re
import unicodedata
from functools import cache
from importlib import resources
from typing import Any

import yaml

from microforge.core.catalog import Catalog
from microforge.core.ideas import load_path
from microforge.core.models import Assignment, BuildResult, SignalRole

ORDRE = {SignalRole.GROUND: 0, SignalRole.POWER: 1}
BUS = {
    SignalRole.I2C_SDA: "Bus I2C, fil de données (SDA)",
    SignalRole.I2C_SCL: "Bus I2C, fil d'horloge (SCL)",
    SignalRole.SPI_MOSI: "Bus SPI, données de la carte vers le module (MOSI)",
    SignalRole.SPI_MISO: "Bus SPI, données du module vers la carte (MISO)",
    SignalRole.SPI_SCK: "Bus SPI, horloge (SCK)",
}


def _data(nom: str) -> Any:
    texte = resources.files("microforge.core").joinpath(f"data/{nom}").read_text(encoding="utf-8")
    return yaml.safe_load(texte)


@cache
def api_doc() -> dict[str, Any]:
    return _data("api_doc.yaml")


@cache
def glossaire() -> tuple[dict[str, Any], ...]:
    return tuple(_data("glossaire.yaml"))


@cache
def quiz() -> dict[int, list[dict[str, Any]]]:
    return {e["etape"]: e["questions"] for e in _data("quiz.yaml")}


def _v(x: float) -> str:
    """Nombre à la française : 3,3 et non 3.3."""
    return f"{x:g}".replace(".", ",")


def _cle(texte: str) -> str:
    sans = unicodedata.normalize("NFKD", texte.lower())
    sans = "".join(c for c in sans if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9()]+", " ", sans).split())


# ------------------------------------------------------------------ montage pas à pas
def pourquoi(a: Assignment, result: BuildResult, catalog: Catalog) -> str:
    """Raison du branchement, tirée du rôle de la broche et des capacités de la broche choisie."""
    board = result.board
    part = next(p for p in result.spec.parts if p.name == a.part)
    comp = catalog.components.get(part.component)
    nom = f"« {a.part} »"
    if a.role == SignalRole.GROUND:
        texte = "Masse : toutes les masses du montage sont reliées, c'est la référence 0 V commune aux signaux."
    elif a.role == SignalRole.POWER:
        volts = board.rails.get(a.board_label)
        plage = (
            f" ; {nom} accepte de {_v(comp.supply_v[0])} à {_v(comp.supply_v[1])} V" if comp else ""
        )
        texte = (
            f"Alimentation : {a.board_label} fournit {_v(volts)} V{plage}."
            if volts
            else f"Alimentation de {nom}."
        )
    elif a.role in BUS:
        texte = f"{BUS[a.role]} : {a.board_label} est la broche par défaut de la carte pour ce bus, partagée par tous les modules qui l'utilisent."
        if a.i2c_address is not None:
            texte += f" {nom} y répond à l'adresse 0x{a.i2c_address:02X}."
    elif a.role == SignalRole.SPI_CS:
        texte = f"Sélection SPI (CS) : une broche propre à {nom}, pour lui signaler que la carte lui parle."
    elif a.role == SignalRole.ADC:
        maxi = 4095 if board.family == "esp32" else 1023
        texte = f"Entrée analogique : {a.board_label} mesure une tension et la convertit en nombre (0 à {maxi})."
        if board.adc2_wifi_conflict:
            texte += " MicroForge choisit une broche de l'ADC1, la seule utilisable quand le Wi-Fi est actif."
    elif a.role == SignalRole.PWM:
        texte = f"Sortie PWM : {a.board_label} module son signal pour régler une luminosité, une vitesse ou l'angle de {nom}."
    elif a.role == SignalRole.GPIO_IN:
        texte = f"Entrée numérique : {a.board_label} lit l'état (haut ou bas) de {nom}."
    elif a.role == SignalRole.GPIO_OUT:
        texte = f"Sortie numérique : {a.board_label} passe à {_v(board.logic_v)} V ou à 0 V pour commander {nom}."
    elif a.role == SignalRole.GPIO_IO:
        texte = f"Données dans les deux sens : {a.board_label} dialogue avec {nom} sur un seul fil."
    elif a.role in (SignalRole.UART_TX, SignalRole.UART_RX):
        texte = f"Liaison série : l'émission (TX) de l'un va sur la réception (RX) de l'autre, ici {a.board_label}."
    else:
        texte = f"{nom} : {a.board_label}."
    for ajout in result.added_parts:
        if ajout.part == a.part and ajout.pin == a.pin:
            texte += f" Par une résistance de {ajout.value} : elle {ajout.reason}."
    if a.note:
        texte += f" {a.note}"
    return texte


def montage(result: BuildResult, catalog: Catalog) -> list[dict[str, Any]]:
    """Étapes de câblage : les masses d'abord, puis les alimentations, puis les signaux."""
    ordre_parts = {p.name: i for i, p in enumerate(result.spec.parts)}
    etapes = sorted(
        result.assignments, key=lambda a: (ORDRE.get(a.role, 2), ordre_parts.get(a.part, 0), a.pin)
    )
    return [
        {
            "part": a.part,
            "pin": a.pin,
            "vers": a.board_label,
            "role": a.role.value,
            "net": a.net,
            "pourquoi": pourquoi(a, result, catalog),
        }
        for a in etapes
    ]


# ------------------------------------------------------------------ programme expliqué
def expliquer_ligne(ligne: str, composants: dict[str, str]) -> list[str]:
    """Explications des appels d'une ligne : fonctions des composants puis fonctions Arduino."""
    doc = api_doc()
    notes = []
    for nom, comp in composants.items():
        for fn in re.findall(rf"\b{re.escape(nom)}_([a-z_0-9]+)\s*\(", ligne):
            texte = doc.get("composants", {}).get(comp, {}).get(fn) or doc["fonctions"].get(fn)
            if texte:
                notes.append(f"{nom}_{fn}() : {texte.format(nom=nom)}")
    for fn, texte in doc["arduino"].items():
        if re.search(rf"(?<![\w.]){re.escape(fn)}\s*\(", ligne):
            notes.append(f"{fn}() : {texte}")
    return notes


def code(result: BuildResult) -> list[dict[str, Any]]:
    """Le programme principal, ligne par ligne ; chaque appel est expliqué à sa première apparition."""
    composants = {p.name: p.component for p in result.spec.parts}
    vues: set[str] = set()
    sortie = []
    for ligne in result.firmware.splitlines():
        notes = [n for n in expliquer_ligne(ligne, composants) if n.split(" : ", 1)[0] not in vues]
        vues |= {n.split(" : ", 1)[0] for n in notes}
        sortie.append({"ligne": ligne, "notes": notes})
    return sortie


# ------------------------------------------------------------------ notions, étape, quiz
def etape_du_modele(template_id: str | None) -> Any:
    return next((e for e in load_path() if template_id in e.templates), None)


def notions(result: BuildResult, catalog: Catalog) -> list[dict[str, str]]:
    """Termes du glossaire présents dans les notions du projet, ses branchements et son programme."""
    template = catalog.templates.get(result.spec.template_id or "")
    textes = list(template.learning) if template else []
    roles = {a.role for a in result.assignments}
    corpus = " | ".join(_cle(t) for t in textes)
    sortie = []
    for entree in glossaire():
        formes = [_cle(entree["terme"]), *(_cle(a) for a in entree.get("aussi", []))]
        trouve = any(re.search(rf"(?<![a-z]){re.escape(f)}(?![a-z])", corpus) for f in formes)
        trouve = trouve or (entree["terme"] == "Bus I2C" and SignalRole.I2C_SDA in roles)
        trouve = trouve or (entree["terme"] == "PWM" and SignalRole.PWM in roles)
        trouve = trouve or (entree["terme"] == "Sortie numérique" and SignalRole.GPIO_OUT in roles)
        trouve = trouve or (entree["terme"] == "Entrée numérique" and SignalRole.GPIO_IN in roles)
        trouve = trouve or (entree["terme"] == "Bus SPI" and SignalRole.SPI_SCK in roles)
        trouve = trouve or (entree["terme"] == "Lecture analogique" and SignalRole.ADC in roles)
        trouve = trouve or (entree["terme"] == "millis()" and "millis()" in result.firmware)
        trouve = trouve or (
            entree["terme"] == "Moniteur série" and "Serial.print" in result.firmware
        )
        if trouve:
            sortie.append({"terme": entree["terme"], "definition": entree["definition"]})
    return sortie


def quiz_du_modele(template_id: str | None) -> dict[str, Any] | None:
    etape = etape_du_modele(template_id)
    if etape is None or etape.etape not in quiz():
        return None
    return {"etape": etape.etape, "titre": etape.titre, "questions": quiz()[etape.etape]}


def apprendre(result: BuildResult, catalog: Catalog) -> dict[str, Any]:
    return {
        "montage": montage(result, catalog),
        "code": code(result),
        "notions": notions(result, catalog),
        "quiz": quiz_du_modele(result.spec.template_id),
    }
