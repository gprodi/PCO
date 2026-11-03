"""Contrôle des règles électriques (ERC) : ce qui peut griller une carte ou faire échouer un montage.

Chaque règle produit un ERCIssue avec un message pédagogique et un correctif concret.
"""

from __future__ import annotations

from microforge.core.allocator import Allocation
from microforge.core.catalog import Catalog
from microforge.core.models import (
    BUS_ROLES,
    BoardDef,
    ERCIssue,
    ProjectSpec,
    Severity,
    SignalRole,
)


def run_erc(spec: ProjectSpec, alloc: Allocation, catalog: Catalog) -> list[ERCIssue]:
    """Applique toutes les règles et renvoie les problèmes détectés (en plus de ceux de l'allocation)."""
    board = catalog.board(spec.board)
    issues: list[ERCIssue] = []
    issues += _level_rules(spec, alloc, catalog, board)
    issues += _rail_budget_rules(spec, alloc, catalog, board)
    issues += _component_rules(spec, alloc, catalog, board)
    issues += _protection_infos(alloc)
    return issues


#: Étages de commande discrets, charges inductives et diodes de roue libre (étape 3).
SWITCHES = {
    "darlington-tip120", "mosfet-irlz44n", "mosfet-irf520", "mosfet-2n7000", "npn-2n2222",
    "npn-s8050", "npn-bc547", "npn-2n3904", "mosfet-module",
}  # fmt: skip
INDUCTIVE = {"dc-motor-tt", "water-pump-5v", "vibration-motor", "fan-12v"}
DIODES = {"diode-1n4007", "diode-1n5819", "diode-1n4148"}


def _rail_v(board: BoardDef, rail: str | None) -> float | None:
    return board.rails.get(rail) if rail else None


def _level_rules(
    spec: ProjectSpec, alloc: Allocation, catalog: Catalog, board: BoardDef
) -> list[ERCIssue]:
    issues: list[ERCIssue] = []
    divided = {(p.part, p.pin) for p in alloc.added_parts if p.kind == "divider"}
    for inst in spec.parts:
        comp = catalog.component(inst.component)
        rail = next((r for r, names in alloc.rails_used.items() if inst.name in names), None)
        supply = _rail_v(board, rail)
        for pin in comp.signal_pins():
            if alloc.gpio_of(inst.name, pin.name) is None:
                continue
            out_v = pin.output_v
            # 1. Sortie 5 V du composant vers une carte 3,3 V non tolérante
            if out_v and out_v > board.logic_v + 0.3 and not board.five_v_tolerant:
                if (inst.name, pin.name) in divided:
                    continue
                if pin.role in BUS_ROLES:
                    issues.append(
                        ERCIssue(
                            code="LEVEL_BUS_5V",
                            severity=Severity.WARNING,
                            message=(
                                f"{inst.name}.{pin.name} : le module tire le bus à {out_v:g} V, "
                                f"or {board.name} est en {board.logic_v:g} V non tolérant."
                            ),
                            fix="Intercaler un level shifter I2C bidirectionnel (BSS138) ou dessouder les pull-ups 5 V du module.",
                            parts=[inst.name],
                        )
                    )
                else:
                    issues.append(
                        ERCIssue(
                            code="LEVEL_5V_INPUT",
                            severity=Severity.ERROR,
                            message=f"{inst.name}.{pin.name} envoie {out_v:g} V sur une entrée {board.logic_v:g} V.",
                            fix="Ajouter un pont diviseur 1 kΩ / 2 kΩ ou un level shifter.",
                            parts=[inst.name],
                        )
                    )
            # 2. Carte 5 V qui pilote un composant 3,3 V (pas tolérant 5 V)
            if board.logic_v > 4 and comp.supply_v[1] < 4.0:
                issues.append(
                    ERCIssue(
                        code="LEVEL_5V_INTO_3V3",
                        severity=Severity.WARNING,
                        message=(
                            f"{inst.name} ({comp.name}) fonctionne en 3,3 V mais {board.name} "
                            f"pilote {pin.name} en 5 V."
                        ),
                        fix="Utiliser un level shifter (ou un module avec régulateur et adaptation de niveaux).",
                        parts=[inst.name],
                    )
                )
                break
            # 3. Composant alimenté en 5 V piloté en 3,3 V
            if (
                supply
                and supply > board.logic_v + 1
                and pin.role in (SignalRole.GPIO_OUT, SignalRole.PWM)
            ):
                if comp.id.startswith("ws2812"):
                    issues.append(
                        ERCIssue(
                            code="LEVEL_WS2812",
                            severity=Severity.WARNING,
                            message=f"{inst.name} : données en {board.logic_v:g} V pour des LED alimentées en {supply:g} V (limite du seuil VIH).",
                            fix="Level shifter 74AHCT125, ou alimenter l'anneau en ~4,5 V via une diode.",
                            parts=[inst.name],
                        )
                    )
                else:
                    issues.append(
                        ERCIssue(
                            code="LEVEL_3V3_DRIVE",
                            severity=Severity.INFO,
                            message=f"{inst.name}.{pin.name} est commandé en {board.logic_v:g} V (module alimenté en {supply:g} V).",
                            fix="Fonctionne avec la plupart des modules (seuil ~2 V) ; sinon ajouter un transistor ou un level shifter.",
                            parts=[inst.name],
                        )
                    )
    return issues


def _rail_budget_rules(
    spec: ProjectSpec, alloc: Allocation, catalog: Catalog, board: BoardDef
) -> list[ERCIssue]:
    issues: list[ERCIssue] = []
    by_name = {p.name: catalog.component(p.component) for p in spec.parts}
    for rail, names in alloc.rails_used.items():
        budget = board.rail_budget_ma.get(rail)
        if budget is None:
            continue
        typical = sum(by_name[n].current_ma for n in names)
        peak = sum(by_name[n].peak_ma or by_name[n].current_ma for n in names)
        if typical > budget:
            issues.append(
                ERCIssue(
                    code="RAIL_OVERLOAD",
                    severity=Severity.ERROR,
                    message=f"Rail {rail} : ~{typical:.0f} mA consommés pour {budget:.0f} mA disponibles.",
                    fix="Alimentation externe dédiée (bloc 5 V 2 A), masses reliées à la carte.",
                    parts=names,
                )
            )
        elif peak > budget:
            issues.append(
                ERCIssue(
                    code="RAIL_PEAK",
                    severity=Severity.WARNING,
                    message=f"Rail {rail} : pics jusqu'à ~{peak:.0f} mA (servo, LED, moteur) pour {budget:.0f} mA disponibles.",
                    fix="Prévoir une alimentation externe et un condensateur 470 µF près des actionneurs.",
                    parts=names,
                )
            )
    return issues


def _component_rules(
    spec: ProjectSpec, alloc: Allocation, catalog: Catalog, board: BoardDef
) -> list[ERCIssue]:
    issues: list[ERCIssue] = []
    ids = [catalog.component(p.component).id for p in spec.parts]
    for inst in spec.parts:
        comp = catalog.component(inst.component)
        if not comp.supports(board):
            issues.append(
                ERCIssue(
                    code="CODE_UNSUPPORTED",
                    severity=Severity.ERROR,
                    message=(
                        f"{inst.name} ({comp.name}) : son code ne compile pas pour {board.name}."
                        + (f" {comp.compat_note}" if comp.compat_note else "")
                    ),
                    fix="Choisir une autre carte ou un composant équivalent compatible.",
                    parts=[inst.name],
                )
            )
    if "relay-module-1ch" in ids:
        issues.append(
            ERCIssue(
                code="SAFETY_MAINS",
                severity=Severity.INFO,
                message="Relais présent : commuter uniquement de la basse tension (≤ 24 V) dans un projet d'apprentissage.",
                fix="Pour du 230 V : boîtier isolant, fusible, et validation par une personne habilitée.",
            )
        )
    switches = SWITCHES & set(ids)
    if INDUCTIVE & set(ids) and switches and not DIODES & set(ids):
        issues.append(
            ERCIssue(
                code="FLYBACK_DIODE",
                severity=Severity.WARNING,
                message=(
                    "Charge inductive (moteur, pompe, ventilateur) commutée par "
                    f"{', '.join(sorted(switches))} sans diode de roue libre : à la coupure, la "
                    "surtension détruit le transistor."
                ),
                fix="Diode 1N4007 (ou 1N5819) en inverse aux bornes de la charge, cathode (anneau) côté +.",
            )
        )
    if "mosfet-irf520" in ids and board.logic_v < 4:
        issues.append(
            ERCIssue(
                code="MOSFET_NOT_LOGIC_LEVEL",
                severity=Severity.WARNING,
                message=(
                    f"L'IRF520 n'est pas à seuil logique : à {board.logic_v:g} V sur la grille il "
                    "conduit mal et chauffe."
                ),
                fix="Utiliser un IRLZ44N (seuil logique) ou un étage transistor de commande.",
            )
        )
    if "ws2812-ring-12" in ids and "capacitor-electrolytic" not in ids:
        issues.append(
            ERCIssue(
                code="LED_STRIP_CAP",
                severity=Severity.INFO,
                message="LED adressables : un appel de courant à l'allumage peut faire redémarrer la carte.",
                fix="Condensateur électrolytique de 1000 µF entre 5 V et GND au plus près de l'anneau, "
                "et 330–470 Ω en série sur la ligne de données (recommandations Adafruit NeoPixel).",
            )
        )
    if "dc-motor-tt" in ids and "l298n-driver" not in ids and not switches:
        issues.append(
            ERCIssue(
                code="MOTOR_DRIVER",
                severity=Severity.ERROR,
                message="Un moteur CC ne se branche jamais directement sur un GPIO.",
                fix="Ajouter un pont en H (L298N, TB6612FNG) ou un transistor MOSFET + diode de roue libre.",
            )
        )
    if "water-pump-5v" in ids and "relay-module-1ch" not in ids and not switches:
        issues.append(
            ERCIssue(
                code="PUMP_DRIVER",
                severity=Severity.ERROR,
                message="La pompe (200 mA) doit être commandée par un relais ou un MOSFET.",
                fix="Ajouter un module relais ou un MOSFET logique (IRLZ44N) + diode 1N4007.",
            )
        )
    if spec.uses_wifi and board.adc2_wifi_conflict:
        adc1 = [
            p.label
            for p in board.pins
            if "adc" in p.caps and "adc2" not in p.caps and not p.reserved
        ]
        issues.append(
            ERCIssue(
                code="ESP32_WIFI_ADC2",
                severity=Severity.INFO,
                message="Wi-Fi actif : l'ADC2 est réservé à la radio, seules les entrées ADC1 "
                f"({', '.join(adc1)}) ont été utilisées pour l'analogique.",
            )
        )
    return issues


def _protection_infos(alloc: Allocation) -> list[ERCIssue]:
    return [
        ERCIssue(
            code=f"AUTO_{p.kind.upper()}",
            severity=Severity.INFO,
            message=f"Ajout automatique : {p.value}{' / ' + p.value_low if p.value_low else ''} ({p.reason}).",
            parts=[p.part],
        )
        for p in alloc.added_parts
    ]
