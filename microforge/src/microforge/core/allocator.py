"""Allocateur de broches déterministe.

Principe de fiabilité de MicroForge : **le LLM ne choisit jamais une broche**. Il propose (au
mieux) une liste de composants ; ce module affecte chaque broche de composant à une broche de
carte en respectant les capacités matérielles :

1. bus partagés d'abord (I2C sur les broches par défaut, SPI avec un CS par périphérique) ;
2. puis chaque signal, dans l'ordre de préférence de la carte, avec les règles :
   * jamais de broche réservée (USB série, flash) ;
   * pas de sortie ni de bidirectionnel sur une broche « entrée seule » ;
   * pas d'INPUT_PULLUP sur une broche sans pull-up interne (ESP32 34–39) ;
   * ADC1 uniquement si le Wi-Fi est utilisé (ESP32) ;
   * broches de démarrage (strapping) réservées aux sorties, en dernier recours ;
3. alimentation : rail compatible avec la plage d'alimentation du composant ;
4. protections automatiques : résistance série (LED), pull-up (1-Wire), pont diviseur (5 V -> 3,3 V).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from microforge.core.catalog import Catalog
from microforge.core.models import (
    INPUT_ROLES,
    AddedPart,
    Assignment,
    BoardDef,
    BoardPin,
    ComponentDef,
    ERCIssue,
    PinSpec,
    ProjectSpec,
    Severity,
    SignalRole,
)

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


class AllocationError(ValueError):
    """Spécification invalide (nom d'instance, composant inconnu…)."""


@dataclass
class Allocation:
    """Résultat de l'allocation."""

    assignments: list[Assignment] = field(default_factory=list)
    added_parts: list[AddedPart] = field(default_factory=list)
    issues: list[ERCIssue] = field(default_factory=list)
    rails_used: dict[str, list[str]] = field(default_factory=dict)  # rail -> instances

    def gpio_of(self, part: str, pin: str) -> int | None:
        for a in self.assignments:
            if a.part == part and a.pin == pin:
                return a.gpio
        return None

    def for_part(self, part: str) -> list[Assignment]:
        return [a for a in self.assignments if a.part == part]


def _fmt_ohm(ohm: int) -> str:
    return f"{ohm / 1000:g} kΩ" if ohm >= 1000 else f"{ohm} Ω"


class PinAllocator:
    """Affecte les broches d'un projet sur une carte."""

    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _order(board: BoardDef) -> dict[int, int]:
        order = {g: i for i, g in enumerate(board.preferred_order)}
        base = len(order)
        for p in sorted(board.pins, key=lambda p: p.gpio):
            order.setdefault(p.gpio, base + p.gpio)
        return order

    def _choose_rail(self, board: BoardDef, comp: ComponentDef) -> str | None:
        lo, hi = comp.supply_v
        fits = {name: v for name, v in board.rails.items() if lo - 0.05 <= v <= hi + 0.05}
        if not fits:
            return None
        if comp.preferred_supply_v is not None:
            for name, v in fits.items():
                if abs(v - comp.preferred_supply_v) < 0.1:
                    return name
        # Priorité au rail égal à la logique de la carte : les signaux sont alors compatibles.
        for name, v in fits.items():
            if abs(v - board.logic_v) < 0.1:
                return name
        return max(fits, key=lambda n: fits[n])

    @staticmethod
    def _pin_ok(
        bp: BoardPin, role: SignalRole, spec: PinSpec, board: BoardDef, uses_wifi: bool
    ) -> bool:
        if bp.reserved:
            return False
        caps = set(bp.caps)
        if role in (SignalRole.GPIO_OUT, SignalRole.GPIO_IO, SignalRole.SPI_CS):
            return "digital" in caps and not bp.input_only
        if role == SignalRole.PWM:
            return "pwm" in caps and not bp.input_only
        if role == SignalRole.GPIO_IN:
            if bp.input_only and (spec.needs_internal_pullup or "digital" not in caps):
                return False
            return "digital" in caps or bp.input_only
        if role == SignalRole.ADC:
            if "adc" not in caps:
                return False
            # ESP32/S2/S3 : l'ADC2 est réservé au Wi-Fi quand celui-ci est actif (donnée de la carte).
            return not (board.adc2_wifi_conflict and uses_wifi and "adc2" in caps)
        return False

    # ------------------------------------------------------------------ principal
    def allocate(self, spec: ProjectSpec) -> Allocation:
        board = self.catalog.board(spec.board)
        result = Allocation()
        used: dict[int, str] = {}
        order = self._order(board)

        parts: list[tuple[str, ComponentDef]] = []
        seen: set[str] = set()
        for inst in spec.parts:
            if not _IDENT.match(inst.name):
                raise AllocationError(
                    f"Nom d'instance invalide {inst.name!r} : minuscules, chiffres et _ uniquement"
                )
            if inst.name in seen:
                raise AllocationError(f"Nom d'instance en double : {inst.name!r}")
            seen.add(inst.name)
            try:
                comp = self.catalog.component(inst.component)
            except KeyError as exc:
                raise AllocationError(str(exc)) from exc
            parts.append((inst.name, comp))

        uses_wifi = spec.uses_wifi
        if uses_wifi and not board.wifi:
            result.issues.append(
                ERCIssue(
                    code="NO_WIFI",
                    severity=Severity.ERROR,
                    message=f"{board.name} n'a pas de Wi-Fi.",
                    fix="Choisir une carte Wi-Fi gérée : ESP32 (toutes variantes sauf H2), ESP8266, Pico W / Pico 2 W.",
                )
            )

        self._allocate_i2c(board, parts, used, result)
        self._allocate_spi(board, parts, used, result, order, uses_wifi)

        # Signaux simples
        for name, comp in parts:
            for pin in comp.signal_pins():
                if pin.role in (*_BUS_I2C, *_BUS_SPI, SignalRole.SPI_CS):
                    continue
                self._allocate_signal(board, name, comp, pin, used, result, order, uses_wifi)

        self._allocate_power(board, parts, result)
        self._add_protections(board, parts, result)
        return result

    # ------------------------------------------------------------------ bus
    def _allocate_i2c(
        self,
        board: BoardDef,
        parts: list[tuple[str, ComponentDef]],
        used: dict[int, str],
        result: Allocation,
    ) -> None:
        i2c_parts = [(n, c) for n, c in parts if any(p.role in _BUS_I2C for p in c.pins)]
        if not i2c_parts:
            return
        if not {"sda", "scl"} <= set(board.default_i2c):
            result.issues.append(
                ERCIssue(
                    code="NO_I2C_BUS",
                    severity=Severity.ERROR,
                    message=f"{board.name} n'expose pas de bus I2C utilisable.",
                    fix="Choisir une autre carte pour ce projet.",
                    parts=[n for n, _ in i2c_parts],
                )
            )
            return
        sda, scl = board.default_i2c["sda"], board.default_i2c["scl"]
        used[sda] = used[scl] = "bus I2C"
        taken: dict[int, str] = {}
        for name, comp in i2c_parts:
            address = next((a for a in comp.i2c_addresses if a not in taken), None)
            note = ""
            if comp.i2c_addresses and address is None:
                result.issues.append(
                    ERCIssue(
                        code="I2C_ADDR_CONFLICT",
                        severity=Severity.ERROR,
                        message=(
                            f"{name} ({comp.name}) : toutes ses adresses I2C "
                            f"{[hex(a) for a in comp.i2c_addresses]} sont déjà prises."
                        ),
                        fix="Utiliser un multiplexeur I2C TCA9548A ou un second bus I2C.",
                        parts=[name, *(taken[a] for a in comp.i2c_addresses if a in taken)],
                    )
                )
            elif address is not None:
                taken[address] = name
                if comp.i2c_addresses and address != comp.i2c_addresses[0]:
                    note = f"adresse alternative {hex(address)} (cavalier/broche d'adresse à configurer)"
                    result.issues.append(
                        ERCIssue(
                            code="I2C_ADDR_ALT",
                            severity=Severity.INFO,
                            message=f"{name} utilise l'adresse {hex(address)} pour éviter un conflit.",
                            fix="Configurer la broche d'adresse du module (ex. AD0 du MPU-6050 au VCC).",
                            parts=[name],
                        )
                    )
            for pin in comp.pins:
                if pin.role == SignalRole.I2C_SDA:
                    gpio, net = sda, "I2C_SDA"
                elif pin.role == SignalRole.I2C_SCL:
                    gpio, net = scl, "I2C_SCL"
                else:
                    continue
                result.assignments.append(
                    Assignment(
                        part=name,
                        pin=pin.name,
                        role=pin.role,
                        gpio=gpio,
                        board_label=board.pin(gpio).label,
                        net=net,
                        note=note,
                        i2c_address=address,
                    )
                )

    def _allocate_spi(
        self,
        board: BoardDef,
        parts: list[tuple[str, ComponentDef]],
        used: dict[int, str],
        result: Allocation,
        order: dict[int, int],
        uses_wifi: bool,
    ) -> None:
        spi_parts = [
            (n, c)
            for n, c in parts
            if any(p.role in (*_BUS_SPI, SignalRole.SPI_CS) for p in c.pins)
        ]
        if not spi_parts:
            return
        if not {"mosi", "miso", "sck"} <= set(board.default_spi):
            result.issues.append(
                ERCIssue(
                    code="NO_SPI_BUS",
                    severity=Severity.ERROR,
                    message=f"{board.name} n'expose pas de bus SPI libre.",
                    fix="Choisir une autre carte pour ce projet.",
                    parts=[n for n, _ in spi_parts],
                )
            )
            return
        bus = {
            SignalRole.SPI_MOSI: board.default_spi["mosi"],
            SignalRole.SPI_MISO: board.default_spi["miso"],
            SignalRole.SPI_SCK: board.default_spi["sck"],
        }
        for gpio in bus.values():
            used[gpio] = "bus SPI"
        default_cs = board.default_spi.get("cs")
        for name, comp in spi_parts:
            for pin in comp.pins:
                if pin.role in bus:
                    gpio = bus[pin.role]
                    result.assignments.append(
                        Assignment(
                            part=name,
                            pin=pin.name,
                            role=pin.role,
                            gpio=gpio,
                            board_label=board.pin(gpio).label,
                            net=pin.role.value.upper(),
                        )
                    )
                elif pin.role == SignalRole.SPI_CS:
                    if default_cs is not None and default_cs not in used:
                        used[default_cs] = f"{name}.{pin.name}"
                        result.assignments.append(
                            Assignment(
                                part=name,
                                pin=pin.name,
                                role=pin.role,
                                gpio=default_cs,
                                board_label=board.pin(default_cs).label,
                                net=f"{name.upper()}_CS",
                            )
                        )
                    else:
                        self._allocate_signal(
                            board, name, comp, pin, used, result, order, uses_wifi
                        )

    # ------------------------------------------------------------------ signaux
    def _allocate_signal(
        self,
        board: BoardDef,
        name: str,
        comp: ComponentDef,
        pin: PinSpec,
        used: dict[int, str],
        result: Allocation,
        order: dict[int, int],
        uses_wifi: bool,
    ) -> None:
        candidates = [
            bp
            for bp in board.pins
            if bp.gpio not in used and self._pin_ok(bp, pin.role, pin, board, uses_wifi)
        ]
        is_input = pin.role in INPUT_ROLES

        def rank(bp: BoardPin) -> tuple[int, int, int]:
            # strapping en dernier ; pour les entrées, privilégier les broches « entrée seule »
            strap = 1 if bp.strapping else 0
            input_first = 0 if (is_input and bp.input_only) else 1
            return (strap, input_first if is_input else 0, order.get(bp.gpio, 999))

        candidates.sort(key=rank)
        # Une entrée tirée ou bidirectionnelle ne va pas sur une broche de démarrage.
        if pin.role in (SignalRole.GPIO_IN, SignalRole.GPIO_IO, SignalRole.ADC):
            candidates = [bp for bp in candidates if not bp.strapping] or []
        if not candidates:
            result.issues.append(
                ERCIssue(
                    code="NO_PIN",
                    severity=Severity.ERROR,
                    message=(
                        f"Plus de broche libre compatible « {pin.role.value} » pour "
                        f"{name}.{pin.name} sur {board.name}."
                    ),
                    fix="Retirer un composant, utiliser un expandeur (PCF8574/MCP23017) ou une carte plus grande (Mega).",
                    parts=[name],
                )
            )
            return
        bp = candidates[0]
        used[bp.gpio] = f"{name}.{pin.name}"
        note = bp.note
        if bp.strapping:
            result.issues.append(
                ERCIssue(
                    code="STRAPPING_PIN",
                    severity=Severity.WARNING,
                    message=f"{name}.{pin.name} utilise {bp.label}, broche lue au démarrage.",
                    fix="Vérifier que le montage ne force pas son niveau pendant le boot.",
                    parts=[name],
                )
            )
        result.assignments.append(
            Assignment(
                part=name,
                pin=pin.name,
                role=pin.role,
                gpio=bp.gpio,
                board_label=bp.label,
                net=f"{name.upper()}_{_net_safe(pin.name)}",
                note=note,
            )
        )

    # ------------------------------------------------------------------ alimentation
    def _allocate_power(
        self, board: BoardDef, parts: list[tuple[str, ComponentDef]], result: Allocation
    ) -> None:
        for name, comp in parts:
            power_pins = [p for p in comp.pins if p.role == SignalRole.POWER]
            ground_pins = [p for p in comp.pins if p.role == SignalRole.GROUND]
            rail = None
            if power_pins:
                rail = self._choose_rail(board, comp)
                if rail is None:
                    result.issues.append(
                        ERCIssue(
                            code="SUPPLY_RANGE",
                            severity=Severity.ERROR,
                            message=(
                                f"{name} ({comp.name}) demande {comp.supply_v[0]}–{comp.supply_v[1]} V : "
                                f"aucun rail compatible sur {board.name} ({board.rails})."
                            ),
                            fix="Ajouter une alimentation externe adaptée (masses reliées).",
                            parts=[name],
                        )
                    )
                else:
                    result.rails_used.setdefault(rail, []).append(name)
            for p in power_pins:
                if rail:
                    result.assignments.append(
                        Assignment(
                            part=name,
                            pin=p.name,
                            role=p.role,
                            board_label=rail,
                            net=_net_safe(rail),
                        )
                    )
            for p in ground_pins:
                # Une LED a sa cathode à la masse : rien à alimenter mais un retour GND.
                result.assignments.append(
                    Assignment(part=name, pin=p.name, role=p.role, board_label="GND", net="GND")
                )

    # ------------------------------------------------------------------ protections
    def _add_protections(
        self, board: BoardDef, parts: list[tuple[str, ComponentDef]], result: Allocation
    ) -> None:
        for name, comp in parts:
            rail = next((r for r, names in result.rails_used.items() if name in names), None)
            for pin in comp.signal_pins():
                if result.gpio_of(name, pin.name) is None:
                    continue
                # Résistance série des LED
                if comp.needs_series_resistor_ohm and pin.role in (
                    SignalRole.GPIO_OUT,
                    SignalRole.PWM,
                ):
                    key = min(
                        comp.needs_series_resistor_ohm,
                        key=lambda k: abs(float(k) - board.logic_v),
                    )
                    ohm = comp.needs_series_resistor_ohm[key]
                    result.added_parts.append(
                        AddedPart(
                            name=f"r_{name}_{_net_safe(pin.name).lower()}",
                            kind="series",
                            part=name,
                            pin=pin.name,
                            value=_fmt_ohm(ohm),
                            reason=f"limite le courant de « {name} » (broche {pin.name}) à ~10 mA en {board.logic_v:g} V".replace(
                                ".", ","
                            ),
                        )
                    )
                # Pull-up externe (sonde 1-Wire nue…)
                if pin.pullup_ohm and not comp.is_module:
                    result.added_parts.append(
                        AddedPart(
                            name=f"r_pullup_{name}",
                            kind="pullup",
                            part=name,
                            pin=pin.name,
                            value=_fmt_ohm(pin.pullup_ohm),
                            rail=rail or next(iter(board.rails)),
                            reason=f"tirage de {name}.{pin.name} vers {rail}",
                        )
                    )
                # Pont diviseur : sortie 5 V vers une entrée non tolérante
                out_v = pin.output_v
                if (
                    out_v is not None
                    and not board.five_v_tolerant
                    and out_v > board.logic_v + 0.3
                    and pin.role in (SignalRole.GPIO_IN, SignalRole.ADC)
                ):
                    result.added_parts.append(
                        AddedPart(
                            name=f"r_div_{name}",
                            kind="divider",
                            part=name,
                            pin=pin.name,
                            value="1 kΩ",
                            value_low="2 kΩ",
                            reason=(
                                f"abaisse {name}.{pin.name} de {out_v:g} V à ~{out_v * 2 / 3:.1f} V "
                                f"pour l'entrée {board.logic_v:g} V"
                            ),
                        )
                    )


_BUS_I2C = (SignalRole.I2C_SDA, SignalRole.I2C_SCL)
_BUS_SPI = (SignalRole.SPI_MOSI, SignalRole.SPI_MISO, SignalRole.SPI_SCK)


def _net_safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").upper() or "N"
