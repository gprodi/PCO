"""Modèles de données du cœur MicroForge (Pydantic).

Vocabulaire :

* **ComponentDef** : un type de composant du catalogue (ex. ``dht22``), avec ses broches.
* **BoardDef** : une carte microcontrôleur (ex. ``esp32-devkit-v1``) et les capacités de chaque GPIO.
* **PartInstance** : un composant utilisé dans un projet, nommé (ex. ``dht`` de type ``dht22``).
* **ProjectSpec** : ce que l'on veut construire (carte + instances + logique).
* **BuildResult** : tout ce qui est généré (affectation des broches, netlist, ERC, code, BOM…).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SignalRole(StrEnum):
    """Rôle électrique d'une broche de composant."""

    POWER = "power"
    GROUND = "ground"
    GPIO_IN = "gpio_in"
    GPIO_OUT = "gpio_out"
    PWM = "pwm"
    ADC = "adc"
    I2C_SDA = "i2c_sda"
    I2C_SCL = "i2c_scl"
    SPI_MOSI = "spi_mosi"
    SPI_MISO = "spi_miso"
    SPI_SCK = "spi_sck"
    SPI_CS = "spi_cs"
    UART_TX = "uart_tx"  # TX du composant -> RX de la carte
    UART_RX = "uart_rx"
    NC = "nc"  # non connecté


BUS_ROLES = {
    SignalRole.I2C_SDA,
    SignalRole.I2C_SCL,
    SignalRole.SPI_MOSI,
    SignalRole.SPI_MISO,
    SignalRole.SPI_SCK,
}
INPUT_ROLES = {SignalRole.GPIO_IN, SignalRole.ADC}


class PinSpec(BaseModel):
    """Broche d'un composant."""

    name: str
    role: SignalRole
    #: Tension de sortie du composant sur cette broche (ex. ECHO du HC-SR04 = 5 V).
    output_v: float | None = None
    #: Résistance de tirage nécessaire si le module ne l'intègre pas.
    pullup_ohm: int | None = None
    description: str = ""


class CodeTemplate(BaseModel):
    """Fragments de code Arduino C++ ; ``{name}`` = nom d'instance, ``{PIN}`` = GPIO affecté."""

    libraries: list[str] = Field(default_factory=list)  # noms arduino-cli / Library Manager
    includes: list[str] = Field(default_factory=list)
    globals: str = ""
    setup: str = ""
    api: str = ""  # fonctions utilitaires exposées à la logique du projet


class ComponentDef(BaseModel):
    """Type de composant du catalogue."""

    id: str
    name: str
    category: str
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    supply_v: tuple[float, float] = (3.3, 5.0)  # plage d'alimentation (min, max)
    preferred_supply_v: float | None = None
    current_ma: float = 1.0  # consommation typique
    peak_ma: float | None = None  # pic (servo, moteur, Wi-Fi…)
    i2c_addresses: list[int] = Field(default_factory=list)
    pins: list[PinSpec] = Field(default_factory=list)
    is_module: bool = True  # breakout prêt à câbler (vs composant nu)
    passive: bool = False  # résistance, condensateur… (pas de code)
    needs_series_resistor_ohm: dict[str, int] | None = None  # LED : {"3.3": 150, "5": 220}
    code: dict[str, CodeTemplate] = Field(default_factory=dict)  # "default", "esp32", "avr", "rp2040"
    wokwi: dict[str, Any] | None = None  # {"type": "...", "pins": {pin: wokwi_pin}, "attrs": {...}}
    kicad: dict[str, str] = Field(default_factory=dict)  # {"symbol": ..., "footprint": ...}
    price_eur: float | None = None
    notes: list[str] = Field(default_factory=list)

    def signal_pins(self) -> list[PinSpec]:
        """Broches à relier à un GPIO de la carte."""
        return [p for p in self.pins if p.role not in (SignalRole.POWER, SignalRole.GROUND, SignalRole.NC)]

    def code_for(self, family: str) -> CodeTemplate:
        """Fragment de code adapté à la famille de MCU (repli sur ``default``)."""
        return self.code.get(family) or self.code.get("default") or CodeTemplate()


class BoardPin(BaseModel):
    """Une broche GPIO de carte et ses capacités."""

    gpio: int
    label: str  # sérigraphie (ex. "D4", "GPIO4", "A0", "GP15")
    caps: list[str] = Field(default_factory=list)  # digital, pwm, adc, adc1, adc2, touch, dac…
    input_only: bool = False
    strapping: bool = False
    reserved: bool = False
    note: str = ""
    wokwi: str | None = None  # nom de la broche dans Wokwi


class BoardDef(BaseModel):
    """Carte microcontrôleur."""

    id: str
    name: str
    family: str  # esp32 | avr | rp2040
    mcu: str
    aliases: list[str] = Field(default_factory=list)
    logic_v: float
    five_v_tolerant: bool = False
    rails: dict[str, float]  # {"3V3": 3.3, "5V": 5.0}
    rail_budget_ma: dict[str, float] = Field(default_factory=dict)
    gpio_max_ma: float = 12
    wifi: bool = False
    bluetooth: bool = False
    fqbn: str = ""
    platformio_board: str = ""
    pins: list[BoardPin]
    default_i2c: dict[str, int] = Field(default_factory=dict)  # {"sda": 21, "scl": 22}
    default_spi: dict[str, int] = Field(default_factory=dict)  # {"mosi":..,"miso":..,"sck":..,"cs":..}
    default_uart: dict[str, int] = Field(default_factory=dict)  # {"rx":.., "tx":..}
    preferred_order: list[int] = Field(default_factory=list)
    wokwi: dict[str, Any] = Field(default_factory=dict)  # {"type": ..., "gnd": "GND.1", "rails": {...}}
    kicad: dict[str, str] = Field(default_factory=dict)
    price_eur: float | None = None
    notes: list[str] = Field(default_factory=list)

    def pin(self, gpio: int) -> BoardPin:
        """Broche par numéro de GPIO."""
        for p in self.pins:
            if p.gpio == gpio:
                return p
        raise KeyError(f"GPIO{gpio} absent de {self.id}")


class PartInstance(BaseModel):
    """Composant utilisé dans un projet."""

    name: str  # identifiant C++ valide : dht, oled, led_rouge…
    component: str  # id du catalogue
    label: str | None = None


class ProjectSpec(BaseModel):
    """Ce que l'on veut construire."""

    title: str
    description: str = ""
    board: str
    parts: list[PartInstance]
    uses_wifi: bool = False
    logic: str = ""  # corps de loop() en C++ (utilise les fonctions api des composants)
    setup_extra: str = ""
    globals_extra: str = ""
    template_id: str | None = None


class ProjectTemplate(BaseModel):
    """Modèle de projet du catalogue (suggestions)."""

    id: str
    title: str
    description: str
    difficulty: int = 1  # 1 débutant – 3 avancé
    tags: list[str] = Field(default_factory=list)
    requires_wifi: bool = False
    board_families: list[str] = Field(default_factory=lambda: ["esp32", "avr", "rp2040"])
    parts: list[PartInstance]
    logic: str
    setup_extra: str = ""
    globals_extra: str = ""
    learning: list[str] = Field(default_factory=list)  # notions apprises


class Assignment(BaseModel):
    """Affectation d'une broche de composant à une broche de carte."""

    part: str
    pin: str
    role: SignalRole
    gpio: int | None = None  # None pour l'alimentation
    board_label: str
    net: str
    note: str = ""


class AddedPart(BaseModel):
    """Composant ajouté automatiquement (résistance série, pont diviseur, pull-up…)."""

    name: str
    component: str
    value: str
    reason: str
    between: tuple[str, str]  # ("dht.DATA", "3V3")


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ERCIssue(BaseModel):
    """Résultat du contrôle électrique."""

    code: str
    severity: Severity
    message: str
    fix: str = ""
    parts: list[str] = Field(default_factory=list)


class NetNode(BaseModel):
    ref: str  # "board" ou nom d'instance
    pin: str


class Net(BaseModel):
    name: str
    nodes: list[NetNode]
    kind: str = "signal"  # signal | power | ground | bus


class BOMLine(BaseModel):
    component: str
    name: str
    quantity: int
    unit_price_eur: float | None = None
    note: str = ""


class BuildResult(BaseModel):
    """Résultat complet de la génération d'un projet."""

    spec: ProjectSpec
    board: BoardDef
    assignments: list[Assignment]
    added_parts: list[AddedPart] = Field(default_factory=list)
    nets: list[Net] = Field(default_factory=list)
    issues: list[ERCIssue] = Field(default_factory=list)
    bom: list[BOMLine] = Field(default_factory=list)
    firmware: str = ""
    libraries: list[str] = Field(default_factory=list)
    wiring_table_md: str = ""
    soldering_guide_md: str = ""
    wiring_svg: str = ""
    wokwi_diagram: dict[str, Any] = Field(default_factory=dict)
    kicad_netlist: str = ""

    @property
    def ok(self) -> bool:
        """Aucune erreur bloquante."""
        return not any(i.severity == Severity.ERROR for i in self.issues)
