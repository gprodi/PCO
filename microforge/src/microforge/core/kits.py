"""Lots de stock « en un clic » : assortiments vendus tels quels aux makers (étape 3).

Chaque lot est une liste de lignes ``{"component_id", "value", "quantity"}`` compatible avec
``POST /v1/inventory/bulk`` (200 lignes maximum par appel).
"""

from __future__ import annotations

from typing import Any

from microforge.core.values import series_values


def _line(component: str, quantity: int, value: float = 0.0) -> dict[str, Any]:
    return {"component_id": component, "value": value, "quantity": quantity}


KITS: dict[str, dict[str, Any]] = {
    "resistances-e12": {
        "titre": "Assortiment de résistances 1/4 W (série E12, 10 Ω à 1 MΩ, × 20 par valeur)",
        "lignes": [_line("resistor", 20, v) for v in series_values("E12", 10, 1e6)],
    },
    "condensateurs-ceramiques": {
        "titre": "Assortiment de condensateurs céramiques (série E6, 10 pF à 1 µF, × 10)",
        "lignes": [_line("capacitor-ceramic", 10, v) for v in series_values("E6", 1e-11, 1e-6)],
    },
    "condensateurs-electrolytiques": {
        "titre": "Assortiment de condensateurs électrolytiques (1 µF à 1000 µF, × 5)",
        "lignes": [_line("capacitor-electrolytic", 5, v) for v in series_values("E6", 1e-6, 1e-3)],
    },
    "semi-conducteurs": {
        "titre": "Diodes et transistors de base",
        "lignes": [
            _line("diode-1n4007", 10),
            _line("diode-1n4148", 10),
            _line("diode-1n5819", 5),
            _line("zener-diode", 5, 3.3),
            _line("zener-diode", 5, 5.1),
            _line("npn-2n2222", 10),
            _line("npn-bc547", 10),
            _line("pnp-bc557", 5),
            _line("mosfet-irlz44n", 2),
            _line("darlington-tip120", 2),
        ],
    },
    "fils-dupont": {
        "titre": "Boîte de fils Dupont 3 × 40 (M-M, M-F, F-F, 20 cm)",
        "lignes": [
            _line("dupont-wire-mm", 40, 20),
            _line("dupont-wire-mf", 40, 20),
            _line("dupont-wire-ff", 40, 20),
        ],
    },
    "kit-debutant": {
        "titre": "Kit débutant générique (Uno, plaque d'essai, LED, boutons, capteurs de base)",
        "lignes": [
            _line("arduino-uno", 1),
            _line("breadboard-830", 1),
            _line("dupont-wire-mm", 40, 20),
            _line("led", 10),
            _line("resistor", 10, 220),
            _line("resistor", 10, 10_000),
            _line("pushbutton", 4),
            _line("potentiometer-10k", 1),
            _line("ldr-module", 1),
            _line("buzzer", 1),
            _line("sg90-servo", 1),
            _line("dht11", 1),
            _line("usb-cable", 1),
        ],
    },
}
