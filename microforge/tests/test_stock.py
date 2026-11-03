"""Étape 3 : le moteur choisit les résistances ajoutées parmi celles du stock."""

from __future__ import annotations

from microforge.core import ProjectBuilder, get_catalog
from microforge.core.models import AddedPart, PartInstance, ProjectSpec
from microforge.core.stock import adapt_resistors

CAT = get_catalog()
BUILDER = ProjectBuilder(CAT)


def part(kind: str, value: str, low: str | None = None) -> AddedPart:
    return AddedPart(
        name=f"r_{kind}", kind=kind, part="x", pin="P", value=value, value_low=low, reason=""
    )


def test_series_resistor_uses_nearest_owned_value_within_safe_range():
    p = part("series", "220 Ω")
    notes = adapt_resistors([p], [10, 330, 1000, 10_000])
    assert p.value == "330 Ω" and p.from_stock and "valeur idéale 220 Ω" in notes[0]
    too_far = part("series", "220 Ω")
    assert adapt_resistors([too_far], [10, 10_000]) == [] and too_far.value == "220 Ω"
    assert not too_far.from_stock  # rien d'acceptable : on garde la valeur à acheter


def test_exact_value_is_marked_from_stock_without_note():
    p = part("pullup", "4,7 kΩ")
    assert adapt_resistors([p], [4700]) == [] and p.from_stock


def test_pullup_range_and_divider_pair():
    up = part("pullup", "4,7 kΩ")
    adapt_resistors([up], [1000, 10_000])
    assert up.value == "10 kΩ"  # 2,2–10 kΩ accepté ; 1 kΩ (trop fort) écarté
    div = part("divider", "1 kΩ", "2 kΩ")
    notes = adapt_resistors([div], [1000, 2200, 4700, 10_000])
    assert (div.value, div.value_low) == ("4,7 kΩ", "10 kΩ") and "sortie ≈ 3.40 V" in notes[0]
    none = part("divider", "1 kΩ", "2 kΩ")
    assert adapt_resistors([none], [100, 220]) == [] and none.value_low == "2 kΩ"


def test_builder_uses_stock_and_bom_says_so():
    spec = ProjectSpec(
        title="LED", board="arduino-uno", parts=[PartInstance(name="voyant", component="led")]
    )
    plain = BUILDER.build(spec)
    assert any(line.note == "220 Ω" for line in plain.bom)
    stocked = BUILDER.build(spec, owned_resistors=[330.0, 10_000.0])
    resistor = next(line for line in stocked.bom if line.component == "resistor")
    assert resistor.note == "330 Ω — dans ton stock"
    assert any(i.code == "STOCK_RESISTOR" for i in stocked.issues)
    assert "330" in stocked.wiring_table_md or "330" in stocked.soldering_guide_md


def test_generate_route_accepts_owned_resistors(ia_client):
    from microforge.common.security import create_access_token, signing_keys

    h = {"Authorization": f"Bearer {create_access_token(1, 'user', signing_keys())}"}
    body = {
        "template_id": "veilleuse-auto",
        "board": "arduino-uno",
        "owned_resistors": [330, 10000],
    }
    r = ia_client.post("/v1/builds/generate", json=body, headers=h)
    assert r.status_code == 200, r.text
    assert any("dans ton stock" in (line.get("note") or "") for line in r.json()["bom"])


def _codes(board: str, *parts: tuple[str, str]) -> set[str]:
    spec = ProjectSpec(
        title="T", board=board, parts=[PartInstance(name=n, component=c) for n, c in parts]
    )
    return {i.code for i in BUILDER.build(spec).issues}


def test_flyback_diode_and_driver_rules():
    pump_tip = _codes("arduino-uno", ("pompe", "water-pump-5v"), ("t", "darlington-tip120"))
    assert "FLYBACK_DIODE" in pump_tip and "PUMP_DRIVER" not in pump_tip  # TIP120 = étage valable
    with_diode = _codes(
        "arduino-uno", ("pompe", "water-pump-5v"), ("t", "darlington-tip120"), ("d", "diode-1n4007")
    )
    assert "FLYBACK_DIODE" not in with_diode
    assert "PUMP_DRIVER" in _codes("arduino-uno", ("pompe", "water-pump-5v"))
    assert "MOTOR_DRIVER" not in _codes(
        "arduino-uno", ("m", "dc-motor-tt"), ("q", "mosfet-irlz44n"), ("d", "diode-1n4007")
    )


def test_irf520_on_3v3_and_led_strip_capacitor():
    assert "MOSFET_NOT_LOGIC_LEVEL" in _codes("esp32-devkit-v1", ("q", "mosfet-irf520"))
    assert "MOSFET_NOT_LOGIC_LEVEL" not in _codes("arduino-uno", ("q", "mosfet-irf520"))
    assert "LED_STRIP_CAP" in _codes("arduino-uno", ("anneau", "ws2812-ring-12"))
    assert "LED_STRIP_CAP" not in _codes(
        "arduino-uno", ("anneau", "ws2812-ring-12"), ("c", "capacitor-electrolytic")
    )


def test_bom_estimates_dupont_wires_from_wiring():
    spec = ProjectSpec(
        title="Météo",
        board="esp32-devkit-v1",
        parts=[
            PartInstance(name="dht", component="dht22"),
            PartInstance(name="ecran", component="ssd1306-i2c"),
        ],
    )
    result = BUILDER.build(spec)
    wires = next(line for line in result.bom if line.component == "dupont-wire-mm")
    # 3 signaux (DATA, SDA, SCL) + 2 × 2 alimentations + 2 rails = 9, + 10 % -> 10
    assert wires.quantity == round((len(result.assignments) + 4 + 2) * 1.1)
    assert "jumper-wires" not in {line.component for line in result.bom}
