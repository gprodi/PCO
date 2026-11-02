"""Code couleur des fils (convention reprise dans le tableau, le SVG et Wokwi)."""

from __future__ import annotations

from microforge.core.models import Net

WIRE_COLORS = {
    "power_5": ("rouge", "#d62828", "red"),
    "power_3": ("orange", "#f77f00", "orange"),
    "ground": ("noir", "#222222", "black"),
    "I2C_SDA": ("bleu", "#1d4ed8", "blue"),
    "I2C_SCL": ("jaune", "#ca8a04", "gold"),
    "SPI": ("violet", "#7c3aed", "purple"),
    "signal": ("vert", "#15803d", "green"),
}


def wire_color(net: Net | str, rail_voltage: float | None = None) -> tuple[str, str, str]:
    """(nom français, hex, couleur Wokwi) pour une net."""
    name = net if isinstance(net, str) else net.name
    kind = None if isinstance(net, str) else net.kind
    if kind == "ground" or name == "GND":
        return WIRE_COLORS["ground"]
    if kind == "power":
        return WIRE_COLORS["power_5"] if (rail_voltage or 5) > 4 else WIRE_COLORS["power_3"]
    if name.startswith("I2C_SDA"):
        return WIRE_COLORS["I2C_SDA"]
    if name.startswith("I2C_SCL"):
        return WIRE_COLORS["I2C_SCL"]
    if name.startswith("SPI_") or name.endswith("_CS"):
        return WIRE_COLORS["SPI"]
    return WIRE_COLORS["signal"]
