"""Tests du cœur MicroForge : catalogue, allocateur, ERC, netlist, sorties, suggestions, génération."""

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import zipfile
from collections import Counter
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from llm_gateway import FakeProvider, Gateway
from microforge.core import ProjectBuilder, get_catalog
from microforge.core.allocator import AllocationError, PinAllocator
from microforge.core.cli import app, parse_stock
from microforge.core.generator import ProjectGenerator, catalog_prompt, component_api
from microforge.core.models import PartInstance, ProjectSpec, Severity, SignalRole
from microforge.core.outputs.bom import Offer, shopping_list
from microforge.core.suggest import suggest_projects
from typer.testing import CliRunner

CAT = get_catalog()
BUILDER = ProjectBuilder(CAT)
STUBS = Path(__file__).parent / "arduino_stubs"


def spec(board: str, *parts: tuple[str, str], wifi: bool = False, logic: str = "") -> ProjectSpec:
    return ProjectSpec(
        title="Test",
        board=board,
        parts=[PartInstance(name=n, component=c) for n, c in parts],
        uses_wifi=wifi,
        logic=logic,
    )


def codes(result) -> set[str]:
    return {i.code for i in result.issues}


# ---------------------------------------------------------------- catalogue
def test_catalog_loaded_and_consistent():
    assert len(CAT.boards) >= 6
    assert len(CAT.components) >= 35
    assert len(CAT.templates) >= 30
    for tpl in CAT.templates.values():
        for part in tpl.parts:
            assert CAT.resolve(part.component), f"{tpl.id}: {part.component}"
    for comp in CAT.components.values():
        names = [p.name for p in comp.pins]
        assert len(names) == len(set(names)), comp.id
        if comp.wokwi:
            assert set(comp.wokwi.get("pins", {})) <= set(names), comp.id


@pytest.mark.parametrize(
    ("alias", "expected"),
    [
        ("oled", "ssd1306-i2c"),
        ("ESP32", "esp32-devkit-v1"),
        ("Potentiomètre", "potentiometer-10k"),
        ("uno", "arduino-uno"),
        ("neopixel", "ws2812-ring-12"),
        ("inconnu-xyz", None),
    ],
)
def test_alias_resolution(alias, expected):
    assert CAT.resolve(alias) == expected


def test_search():
    ids = [item.id for item in CAT.search("capteur temperature")]
    assert "dht22" in ids or "ds18b20" in ids


def test_mega_and_pico_pins_expanded():
    assert len(CAT.board("arduino-mega").pins) > 60
    assert CAT.board("rpi-pico").pin(26).label == "GP26"
    assert CAT.board("arduino-mega").pin(54).label == "A0"


# ---------------------------------------------------------------- allocateur
def test_esp32_input_prefers_input_only_and_avoids_strapping():
    r = BUILDER.build(spec("esp32-devkit-v1", ("sonar", "hc-sr04")))
    echo = next(a for a in r.assignments if a.pin == "ECHO")
    assert CAT.board("esp32-devkit-v1").pin(echo.gpio).input_only
    assert "AUTO_DIVIDER" in codes(r)
    assert r.ok


def test_esp32_wifi_forces_adc1():
    r = BUILDER.build(
        spec("esp32-devkit-v1", ("pot", "potentiometer-10k"), ("ldr", "ldr-module"), wifi=True)
    )
    board = CAT.board("esp32-devkit-v1")
    for a in r.assignments:
        if a.role == SignalRole.ADC:
            assert "adc1" in board.pin(a.gpio).caps


def test_button_never_on_input_only_pin():
    parts = [(f"b{i}", "pushbutton") for i in range(8)]
    r = BUILDER.build(spec("esp32-devkit-v1", *parts))
    board = CAT.board("esp32-devkit-v1")
    for a in r.assignments:
        if a.gpio is not None:
            assert not board.pin(a.gpio).input_only
            assert not board.pin(a.gpio).strapping


def test_i2c_shared_bus_and_address_conflict_resolution():
    r = BUILDER.build(
        spec("arduino-uno", ("rtc", "ds3231-rtc"), ("imu", "mpu6050"), ("ecran", "ssd1306-i2c"))
    )
    sda = {a.gpio for a in r.assignments if a.role == SignalRole.I2C_SDA}
    assert sda == {18}
    imu = next(a for a in r.assignments if a.part == "imu" and a.i2c_address is not None)
    assert imu.i2c_address == 0x69
    assert "I2C_ADDR_ALT" in codes(r)


def test_i2c_unresolvable_conflict_is_error():
    r = BUILDER.build(spec("arduino-uno", ("a", "ds3231-rtc"), ("b", "ds3231-rtc")))
    assert "I2C_ADDR_CONFLICT" in codes(r)
    assert not r.ok


def test_spi_two_devices_get_distinct_cs():
    r = BUILDER.build(spec("esp32-devkit-v1", ("rfid", "rc522-rfid"), ("sd", "microsd-module")))
    cs = [a.gpio for a in r.assignments if a.role == SignalRole.SPI_CS]
    assert len(cs) == 2 and len(set(cs)) == 2


def test_too_many_parts_reports_no_pin():
    parts = [(f"led{i}", "led") for i in range(30)]
    r = BUILDER.build(spec("arduino-nano", *parts))
    assert "NO_PIN" in codes(r)
    assert not r.ok


def test_invalid_specs_raise():
    with pytest.raises(AllocationError):
        PinAllocator(CAT).allocate(spec("arduino-uno", ("Bad-Name", "led")))
    with pytest.raises(AllocationError):
        PinAllocator(CAT).allocate(spec("arduino-uno", ("a", "led"), ("a", "led")))
    with pytest.raises(AllocationError):
        PinAllocator(CAT).allocate(spec("arduino-uno", ("a", "flux-capacitor")))


SIGNAL_COMPONENTS = [
    "led",
    "pushbutton",
    "potentiometer-10k",
    "dht22",
    "buzzer",
    "relay-module-1ch",
    "pir-hc-sr501",
    "sg90-servo",
    "hc-sr04",
    "ssd1306-i2c",
    "ldr-module",
]


@settings(max_examples=60, deadline=None)
@given(
    board=st.sampled_from(
        ["esp32-devkit-v1", "arduino-uno", "arduino-nano", "rpi-pico", "arduino-mega"]
    ),
    comps=st.lists(st.sampled_from(SIGNAL_COMPONENTS), min_size=1, max_size=8),
    wifi=st.booleans(),
)
def test_allocation_properties(board, comps, wifi):
    """Propriétés : jamais deux signaux sur un même GPIO (hors bus), jamais de broche réservée."""
    b = CAT.board(board)
    if wifi and not b.wifi:
        wifi = False
    s = spec(board, *[(f"c{i}", c) for i, c in enumerate(comps)], wifi=wifi)
    alloc = PinAllocator(CAT).allocate(s)
    gpios = [
        a.gpio
        for a in alloc.assignments
        if a.gpio is not None and not a.net.startswith(("I2C_", "SPI_"))
    ]
    assert len(gpios) == len(set(gpios))
    for a in alloc.assignments:
        if a.gpio is not None:
            pin = b.pin(a.gpio)
            assert not pin.reserved
            if a.role in (SignalRole.GPIO_OUT, SignalRole.GPIO_IO, SignalRole.PWM):
                assert not pin.input_only


# ---------------------------------------------------------------- ERC
@pytest.mark.parametrize(
    ("board", "parts", "expected", "severity"),
    [
        ("arduino-uno", [("capteur", "bme280")], "LEVEL_5V_INTO_3V3", Severity.WARNING),
        ("esp32-devkit-v1", [("lcd", "lcd1602-i2c")], "LEVEL_BUS_5V", Severity.WARNING),
        ("esp32-devkit-v1", [("anneau", "ws2812-ring-12")], "LEVEL_WS2812", Severity.WARNING),
        (
            "arduino-uno",
            [("s1", "sg90-servo"), ("s2", "sg90-servo")],
            "RAIL_PEAK",
            Severity.WARNING,
        ),
        ("arduino-uno", [("m", "dc-motor-tt")], "MOTOR_DRIVER", Severity.ERROR),
        ("arduino-uno", [("p", "water-pump-5v")], "PUMP_DRIVER", Severity.ERROR),
        ("arduino-uno", [("r", "relay-module-1ch")], "SAFETY_MAINS", Severity.INFO),
        ("arduino-uno", [("sonde", "ds18b20")], "AUTO_PULLUP", Severity.INFO),
    ],
)
def test_erc_rules(board, parts, expected, severity):
    r = BUILDER.build(spec(board, *parts))
    issue = next((i for i in r.issues if i.code == expected), None)
    assert issue is not None, codes(r)
    assert issue.severity == severity


def test_rail_overload_error():
    parts = [(f"gaz{i}", "mq2-gas") for i in range(4)]  # 4 × 150 mA sur un rail de 400 mA
    r = BUILDER.build(spec("arduino-mega", *parts))
    assert "RAIL_OVERLOAD" in codes(r)


def test_wifi_on_uno_is_error():
    r = BUILDER.build(spec("arduino-uno", ("led", "led"), wifi=True))
    assert "NO_WIFI" in codes(r)


# ---------------------------------------------------------------- netlist & sorties
def test_netlist_series_resistor_and_divider():
    r = BUILDER.build(spec("esp32-devkit-v1", ("led", "led"), ("sonar", "hc-sr04")))
    names = {n.name for n in r.nets}
    assert "LED_A" in names and "LED_A_R" in names
    assert "SONAR_ECHO_5V" in names
    gnd = next(n for n in r.nets if n.name == "GND")
    assert any(node.ref == "r_div_sonar_bas" for node in gnd.nodes)
    for net in r.nets:
        assert len(net.nodes) >= 2, net.name


def test_wokwi_diagram_is_consistent():
    r = BUILDER.build(BUILDER.spec_from_template("radar-de-recul", "arduino-uno"))
    d = r.wokwi_diagram
    ids = {p["id"] for p in d["parts"]}
    assert len(ids) == len(d["parts"])
    assert d["parts"][0]["type"] == "wokwi-arduino-uno"
    for a, b, color, path in d["connections"]:
        assert a.split(":")[0] in ids and b.split(":")[0] in ids
        assert isinstance(color, str) and path == []
    json.dumps(d)


def test_wokwi_lists_missing_parts():
    r = BUILDER.build(spec("esp32-devkit-v1", ("c", "bme280")))
    assert r.wokwi_diagram["microforge"]["missing_parts"]


def test_kicad_netlist_structure():
    r = BUILDER.build(BUILDER.spec_from_template("station-meteo-oled", "arduino-uno"))
    net = r.kicad_netlist
    assert net.startswith('(export (version "E")')
    assert net.count("(") == net.count(")")
    assert '(name "GND")' in net and '(ref "J1")' in net


def test_svg_accessible():
    r = BUILDER.build(BUILDER.spec_from_template("serrure-rfid", "esp32-devkit-v1"))
    assert 'role="img"' in r.wiring_svg and "<title" in r.wiring_svg and "<desc" in r.wiring_svg


def test_guide_and_table_content():
    r = BUILDER.build(BUILDER.spec_from_template("radar-de-recul", "esp32-devkit-v1"))
    assert "pont diviseur" in r.wiring_table_md
    assert "Contrôles au multimètre" in r.soldering_guide_md
    assert "Dépannage" in r.soldering_guide_md


def test_bundle_zip_contains_everything():
    r = BUILDER.build(BUILDER.spec_from_template("horloge-ntp-oled", "esp32-devkit-v1"))
    data = BUILDER.bundle(r)
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    for expected in (
        "cablage.md",
        "guide-montage.md",
        "wokwi/diagram.json",
        "kicad/projet.net",
        "platformio.ini",
        "README.md",
        "secrets.h",
    ):
        assert any(n.endswith(expected) for n in names), expected


# ---------------------------------------------------------------- BOM & liste d'achat
def test_bom_and_shopping_list_with_offers():
    r = BUILDER.build(BUILDER.spec_from_template("radar-de-recul", "esp32-devkit-v1"))
    ids = Counter(line.component for line in r.bom)
    assert ids["esp32-devkit-v1"] == 1 and ids["resistor"] >= 2
    inventory = {"esp32-devkit-v1": 1, "led": 5}
    offers = [
        Offer(supplier="Boutique A", component="hc-sr04", unit_price_eur=1.9, url="https://a"),
        Offer(supplier="Boutique B", component="hc-sr04", unit_price_eur=2.4),
        Offer(supplier="Boutique C", component="hc-sr04", unit_price_eur=0.5, stock=0),
    ]
    sl = shopping_list(r.bom, inventory, offers)
    to_buy = {line.component: line for line in sl.to_buy}
    assert "esp32-devkit-v1" not in to_buy and "led" not in to_buy
    assert to_buy["hc-sr04"].supplier == "Boutique A"
    assert sl.total_eur > 0
    assert "Total estimé" in sl.to_markdown()
    assert sl.to_csv().startswith("composant;")
    assert "Boutique A" in sl.by_supplier()


def test_shopping_nothing_to_buy():
    r = BUILDER.build(spec("arduino-uno", ("b", "pushbutton")))
    inv = {line.component: line.quantity for line in r.bom}
    assert shopping_list(r.bom, inv).to_markdown().startswith("Tu as déjà tout")


# ---------------------------------------------------------------- suggestions
def test_suggestions_rank_feasible_first():
    stock = {"esp32": 1, "dht22": 1, "oled": 1, "led": 3, "bouton": 2, "buzzer": 1}
    sugg = suggest_projects(stock, limit=5)
    assert sugg and sugg[0].feasible_now
    assert all(s.board.id == "esp32-devkit-v1" for s in sugg)
    d = sugg[0].to_dict()
    assert {"title", "missing", "score", "board"} <= set(d)


def test_suggestions_without_board_propose_cheapest():
    sugg = suggest_projects({"led": 3, "pushbutton": 1}, limit=3)
    assert sugg and not sugg[0].board_owned


# ---------------------------------------------------------------- firmware
def test_firmware_structure_and_constants():
    r = BUILDER.build(BUILDER.spec_from_template("station-meteo-oled", "arduino-uno"))
    header = next(v for k, v in r.firmware_files.items() if k.endswith("mf_components.h"))
    assert "const uint8_t PIN_DHT_DATA" in header
    assert header.count("Wire.begin();") == 1
    assert "0x3C" in header
    assert '#include "mf_components.h"' in r.firmware
    assert set(r.libraries) >= {"DHT sensor library", "Adafruit SSD1306"}


def test_esp32_servo_uses_esp32servo():
    r = BUILDER.build(BUILDER.spec_from_template("barriere-servo", "esp32-devkit-v1"))
    assert "ESP32Servo" in r.libraries


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ absent")
@pytest.mark.parametrize("tid", sorted(CAT.templates))
def test_generated_firmware_compiles_syntax(tid, tmp_path):
    """Chaque modèle génère du C++ valide (vérifié avec des en-têtes Arduino simulés)."""
    tpl = CAT.templates[tid]
    board = {"esp32": "esp32-devkit-v1", "avr": "arduino-uno", "rp2040": "rpi-pico-w"}[
        tpl.board_families[0]
    ]
    defines = {
        "esp32-devkit-v1": "-DESP32",
        "arduino-uno": "-DARDUINO_ARCH_AVR",
        "rpi-pico-w": "-DARDUINO_ARCH_RP2040",
    }
    r = BUILDER.build(BUILDER.spec_from_template(tid, board))
    for rel, content in r.firmware_files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    ino = next(tmp_path.rglob("*.ino"))
    proc = subprocess.run(
        [
            "g++",
            "-fsyntax-only",
            "-std=gnu++17",
            "-Wall",
            "-Wno-unused-function",
            f"-I{STUBS}",
            defines[board],
            "-x",
            "c++",
            "-include",
            "Arduino.h",
            str(ino),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


# ---------------------------------------------------------------- génération LLM
def test_component_api_and_prompt():
    api = component_api(CAT, "dht22")
    assert any("<nom>_temperature()" in f for f in api)
    prompt = catalog_prompt(CAT)
    assert "esp32-devkit-v1" in prompt and "ssd1306-i2c" in prompt


def test_generator_valid_idea_from_fake_llm():
    idea = {
        "title": "Thermomètre",
        "description": "Affiche la température",
        "board": "ESP32",
        "uses_wifi": False,
        "parts": [
            {"name": "Capteur Temp", "component": "dht22"},
            {"name": "ecran", "component": "oled"},
        ],
        "logic": "ecran_print(String(capteur_temp_temperature(), 1));\ndelay(1000);",
        "globals_extra": "",
        "setup_extra": "",
    }
    gen = ProjectGenerator(Gateway.fake(FakeProvider({"thermom": idea})), CAT)
    s = gen.from_goal("je veux un thermomètre")
    assert s.board == "esp32-devkit-v1"
    assert [p.component for p in s.parts] == ["dht22", "ssd1306-i2c"]
    assert s.parts[0].name == "capteur_temp"
    assert BUILDER.build(s).ok


def test_generator_falls_back_to_template_when_llm_invalid():
    bad = {"title": "x", "description": "", "board": "commodore64", "parts": [], "logic": ""}
    gen = ProjectGenerator(Gateway.fake(FakeProvider({"radar": bad})), CAT)
    s = gen.from_goal("un radar de recul pour mon garage")
    assert s.template_id == "radar-de-recul"


def test_generator_ideas_from_inventory():
    ideas = {
        "ideas": [
            {
                "title": "Veilleuse",
                "description": "",
                "board": "arduino-uno",
                "parts": [{"name": "led", "component": "led"}],
                "logic": "led_on();",
            },
            {
                "title": "KO",
                "description": "",
                "board": "arduino-uno",
                "parts": [{"name": "x", "component": "inconnu"}],
                "logic": "",
            },
        ]
    }
    gen = ProjectGenerator(Gateway.fake(FakeProvider({"stock": ideas})), CAT)
    specs = gen.ideas_from_inventory({"arduino-uno": 1, "led": 2})
    assert [s.title for s in specs] == ["Veilleuse"]


# ---------------------------------------------------------------- CLI
def test_parse_stock():
    assert parse_stock("esp32=1, dht22 = 2, led") == {"esp32": 1, "dht22": 2, "led": 1}


def test_cli_commands(tmp_path, monkeypatch):
    runner = CliRunner()
    assert runner.invoke(app, ["catalog"]).exit_code == 0
    res = runner.invoke(app, ["suggest", "--stock", "uno=1,led=3,pushbutton=1"])
    assert res.exit_code == 0 and "Feu tricolore" in res.output
    res = runner.invoke(
        app, ["build", "veilleuse-auto", "--board", "arduino-uno", "--out", str(tmp_path)]
    )
    assert res.exit_code == 0
    assert (tmp_path / "veilleuse-auto" / "cablage.md").exists()
    res = runner.invoke(app, ["build", "veilleuse-auto", "--out", str(tmp_path), "--zip"])
    assert res.exit_code == 0 and list(tmp_path.glob("veilleuse-auto/*.zip"))
    monkeypatch.setenv("LLM_CHAIN", "fake")
    monkeypatch.setenv("LLM_PROFILE", "cpu")
    res = runner.invoke(app, ["goal", "une veilleuse automatique", "--out", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert re.search(r'"ok": (true|false)', res.output)
