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


CAPACITY_CODES = {"NO_PIN", "NO_I2C_BUS", "NO_SPI_BUS"}


def _board_for(tid: str, family: str):
    """Première carte de la famille (référence d'abord) sur laquelle le projet est réalisable.

    Renvoie (carte, None) ou (None, raison) quand aucune carte de la famille n'a assez de broches :
    c'est une limite matérielle signalée par le moteur, pas une erreur de génération.
    """
    rep = CAT.representative(family)
    candidates = [rep] + [
        b for b in CAT.boards_for_template(tid) if b.family == family and b.id != rep.id
    ]
    reasons = []
    for board in candidates:
        if not CAT.template_fits(tid, board):
            continue
        r = BUILDER.build(BUILDER.spec_from_template(tid, board.id))
        errors = [i for i in r.issues if i.severity.value == "error"]
        if not errors:
            return board.id, None
        assert {i.code for i in errors} <= CAPACITY_CODES | {"CODEGEN"}, [i.message for i in errors]
        reasons.append(f"{board.id}: {errors[0].message}")
    return None, "; ".join(reasons)


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ absent")
@pytest.mark.parametrize(
    ("tid", "family"),
    [(tid, fam) for tid in sorted(CAT.templates) for fam in CAT.template_families(tid)],
)
def test_generated_firmware_compiles_syntax(tid, family, tmp_path):
    """Chaque modèle génère du C++ valide sur chaque famille compatible (en-têtes Arduino simulés)."""
    board, reason = _board_for(tid, family)
    if board is None:
        pytest.skip(f"pas assez de broches dans la famille {family} : {reason}")
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
            CAT.families[family].gpp_define,
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


# ---------------------------------------------------------------- idées par thème
def test_ideas_catalog_consistent():
    from microforge.core.ideas import load_themes

    themes = load_themes()
    assert {t.id for t in themes} >= {
        "plantes",
        "interieur",
        "exterieur",
        "securite",
        "robotique",
        "jeux",
    }
    total = 0
    for t in themes:
        assert len(t.idees) >= 4, t.id
        for idea in t.idees:
            total += 1
            for comp in idea.composants:
                assert CAT.resolve(comp) == comp, f"{t.id}/{idea.titre}: {comp}"
            if idea.template:
                assert idea.template in CAT.templates, idea.template
    assert total >= 60
    used = {i.template for t in themes for i in t.idees if i.template}
    assert used == set(CAT.templates), set(CAT.templates) - used


def test_explore_with_inventory():
    from microforge.core.ideas import explore, goal_for, load_themes

    plain = explore()
    assert plain[0]["idees"][0]["realisable"] is None
    res = explore({"esp32": 1, "soil-moisture-capacitive": 1, "rgb-led": 1})
    plantes = next(t for t in res if t["id"] == "plantes")
    first = plantes["idees"][0]
    assert first["titre"] == "Moniteur d'humidité du sol à LED" and first["realisable"]
    assert any(i["manquants"] for i in plantes["idees"])
    assert "Composants suggérés" in goal_for(load_themes()[0].idees[1])


# ---------------------------------------------------------------- références externes
def test_every_template_has_public_references():
    """Chaque modèle renvoie vers au moins un tutoriel public équivalent (recoupement)."""
    urls = []
    for tid, tpl in CAT.templates.items():
        assert tpl.references, f"{tid} : aucune référence dans data/references.yaml"
        for ref in tpl.references:
            assert ref.url.startswith("https://"), ref.url
            urls.append(ref.url)
    assert len(urls) == len(set(urls)), "URL de référence en double"


def test_references_file_has_no_unknown_template():
    from importlib import resources

    import yaml

    refs = yaml.safe_load(
        resources.files("microforge.core.data").joinpath("references.yaml").read_text()
    )
    assert set(refs) <= set(CAT.templates)


def test_readme_states_verification_level():
    r = BUILDER.build(BUILDER.spec_from_template("alarme-porte", "arduino-uno"))
    readme = BUILDER.readme(r)
    assert "Niveau de vérification" in readme
    assert "Pas encore monté sur du vrai matériel" in readme
    assert "arduinogetstarted.com" in readme


def test_cli_lists_libraries_per_board():
    from microforge.core.cli import app, templates_for_board
    from typer.testing import CliRunner

    uno = CAT.boards["arduino-uno"]
    ids = templates_for_board(CAT, uno)
    assert "alarme-porte" in ids and all(not CAT.templates[t].requires_wifi for t in ids)
    out = CliRunner().invoke(app, ["libs", "--fqbn", "arduino:avr:uno"]).output
    assert "IRremote" in out and "ESP32Servo" not in out
    assert "LedControl" not in out  # pilote MAX7219 intégré (incompatible ESP32 3.x)


def test_cli_sketch_dir_ignores_wokwi_folder(tmp_path):
    """Régression CI : le dossier wokwi/ (sketch.ino) ne doit pas être pris pour le sketch."""
    from microforge.core.cli import sketch_dir, write_project

    for tid in ("station-meteo-oled", "alarme-porte", "veilleuse-auto"):
        r = BUILDER.build(BUILDER.spec_from_template(tid, "arduino-uno"))
        write_project(BUILDER, r, tmp_path / tid)
        d = sketch_dir(tmp_path / tid)
        assert d.name != "wokwi" and (d / f"{d.name}.ino").exists()


def test_no_avr_only_header_outside_avr_variants():
    """Régression CI ESP32 : un en-tête <avr/...> ne peut apparaître que dans une variante avr."""
    import re

    for comp in CAT.components.values():
        for family, tpl in comp.code.items():
            text = "\n".join(tpl.includes) + tpl.globals + tpl.setup + tpl.api
            if re.search(r"#include\s*<avr/", text):
                assert family == "avr", f"{comp.id} ({family}) inclut un en-tête AVR"
            assert "LedControl" not in tpl.libraries, comp.id


# ---------------------------------------------------------------- catalogue de cartes
def test_each_family_has_exactly_one_representative():
    for fam in CAT.families:
        reps = [b.id for b in CAT.boards.values() if b.family == fam and b.representative]
        assert len(reps) == 1, (fam, reps)
    assert CAT.representative("rp2040").wifi  # couvre aussi les projets Wi-Fi de la famille


@pytest.mark.parametrize("board_id", sorted(CAT.boards))
def test_board_definition_is_consistent(board_id):
    """Source officielle, FQBN du bon cœur, bus par défaut sur des broches existantes et libres."""
    board = CAT.boards[board_id]
    fam = CAT.families[board.family]
    assert board.source.startswith("https://"), "brochage officiel manquant"
    assert board.fqbn.startswith(fam.core + ":"), (board.fqbn, fam.core)
    pins = {p.gpio: p for p in board.pins}
    for bus in (board.default_i2c, board.default_spi):
        for role, gpio in bus.items():
            assert gpio in pins, f"{role}={gpio} absent des broches"
            assert not pins[gpio].reserved, f"{role}={gpio} est réservée"
    for role in ("sda", "scl", "mosi", "sck", "cs"):
        gpio = board.default_i2c.get(role, board.default_spi.get(role))
        if gpio is not None:
            assert not pins[gpio].input_only, f"{role}={gpio} est en entrée seule"


def test_ci_matrix_covers_every_family_and_chip_variant():
    from microforge.core.cli import app
    from typer.testing import CliRunner

    res = CliRunner().invoke(app, ["ci-matrix"])
    include = json.loads(res.output)["include"]
    assert {e["family"] for e in include} == set(CAT.families)
    assert sum(e["smoke"] for e in include) == len(CAT.families)  # fumée : une fois par famille
    fqbns = {e["fqbn"] for e in include}
    assert {"esp32:esp32:esp32s3", "esp32:esp32:esp32c3", "esp32:esp32:esp32c6"} <= fqbns
