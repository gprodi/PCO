"""Atelier virtuel : transpilation C++ -> JS et exécution de chaque projet dans Node (temps virtuel)."""

from __future__ import annotations

import json
import shutil
import subprocess
from importlib import resources
from pathlib import Path

import pytest
from microforge.core import get_catalog
from microforge.core.builder import ProjectBuilder
from microforge.core.models import ProjectSpec
from microforge.sim import TranspileError, runtime_js, simulation_payload, transpile
from microforge.sim.transpile import component_api, tokenize

CAT = get_catalog()
BUILDER = ProjectBuilder(CAT)
RUNNER = Path(__file__).parent / "sim_runner.cjs"
MFSIM = resources.files("microforge.sim").joinpath("static/mfsim.js")
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node absent")


def _spec(tid: str) -> ProjectSpec:
    board = "esp32-devkit-v1"
    if not CAT.template_fits(tid, CAT.boards[board]):
        board = CAT.boards_for_template(tid)[0].id
    return BUILDER.spec_from_template(tid, board)


def run(payload: dict, tmp_path: Path, until: int = 60_000, events: list | None = None) -> dict:
    (tmp_path / "payload.json").write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "scenario.json").write_text(json.dumps({"until": until, "events": events or []}))
    proc = subprocess.run(
        [
            "node",
            str(RUNNER),
            str(MFSIM),
            str(tmp_path / "payload.json"),
            str(tmp_path / "scenario.json"),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-3000:]
    return json.loads(proc.stdout)


def _stimuli(payload: dict) -> list:
    """Bouge chaque contrôle de chaque capteur : extrêmes des curseurs, appuis, événements."""
    sim_inputs = {
        "pushbutton": [("press", "pressed"), ("release", "pressed")],
        "ttp223-touch": [("press", "touch"), ("release", "touch")],
        "pir-hc-sr501": [("press", "pass"), ("release", "pass")],
        "rcwl-0516": [("press", "pass"), ("release", "pass")],
        "ky038-sound": [("press", "clap"), ("release", "clap")],
        "keypad-4x4": [("fire", "key", k) for k in "1234#"],
        "ir-receiver": [("fire", "code", "69")],
        "rc522-rfid": [("fire", "badge", "DE AD BE EF"), ("fire", "badge", "12 34 56 78")],
        "rotary-encoder-ky040": [("fire", "turn", "1"), ("fire", "turn", "-1")],
        "reed-switch": [("set", "open", True), ("set", "open", False)],
        "tcrt5000-line": [("set", "line", True), ("set", "line", False)],
        "dht22": [("set", "temperature", 40), ("set", "temperature", 10)],
        "ds18b20": [("set", "temperature", 30), ("set", "temperature", 12)],
        "potentiometer-10k": [("set", "position", 100), ("set", "position", 0)],
        "hc-sr04": [("set", "distance", 10), ("set", "distance", 450)],
        "ldr-module": [("set", "light", 5), ("set", "light", 90)],
        "soil-moisture-capacitive": [("set", "moisture", 10), ("set", "moisture", 80)],
        "hx711-load-cell": [("set", "mass", 1200), ("set", "mass", 0)],
        "water-level-sensor": [("set", "level", 80), ("set", "level", 0)],
        "flame-sensor": [("set", "intensity", 90), ("set", "intensity", 0)],
        "mq2-gas": [("set", "level", 90), ("set", "level", 5)],
        "mq135-air": [("set", "level", 90), ("set", "level", 5)],
        "joystick-analog": [("set", "x", 100), ("set", "y", -100)],
    }
    events, t = [], 2_000
    for part in payload["parts"]:
        for step in sim_inputs.get(part["component"], []):
            action, key, *value = step
            events.append([t, part["name"], action, key, value[0] if value else None])
            t += 700
    return events


# ---------------------------------------------------------------- transpileur
def test_tokenizer_merges_adjacent_strings_and_skips_comments():
    toks = tokenize('String s = "a" "b"; /* x */ // y\n')
    assert [t.text for t in toks][:5] == ["String", "s", "=", '"ab"', ";"]


def test_component_api_signatures():
    api = component_api(
        'void ${name}_print(const String& l1, const String& l2 = "", bool big = false) {}\n'
        "float ${name}_lux() { return 1; }\nvoid ${name}_show(const byte img[8]) {}\n"
        "bool ${name}_append(const char* path, const String& line) { return true; }"
    )
    assert api["print"].params == ["String", "String", "bool"] and api["lux"].ret == "float"
    assert api["show"].params == ["arr:u8"] and api["append"].params == ["cstr", "String"]


@pytest.mark.parametrize("tid", sorted(CAT.templates))
def test_every_template_transpiles(tid):
    js = transpile(CAT, _spec(tid))
    assert "async function loop()" in js and "return { setup, loop };" in js


def test_unknown_constructs_are_rejected():
    spec = ProjectSpec(title="t", board="arduino-uno", parts=[], logic="inconnue();")
    with pytest.raises(TranspileError, match="inconnue"):
        transpile(CAT, spec)
    bad = ProjectSpec(title="t", board="arduino-uno", parts=[], logic="int x = y;")
    with pytest.raises(TranspileError, match="identifiant inconnu"):
        transpile(CAT, bad)


def test_runtime_is_packaged():
    assert "class Simulation" in runtime_js()


# ---------------------------------------------------------------- exécution (Node)
SEMANTICS = """
uint8_t a = 250; a += 10; Serial.println(a);
int q = 7 / 2; Serial.println(q);
int r = -7 / 2; Serial.println(r);
float f = 7 / 2.0; Serial.println(f);
Serial.println(String(3.14159, 3));
unsigned long u = 0; u = u - 1; Serial.println(u);
int8_t s = 127; s++; Serial.println(s);
char k = 'A'; String t = "x"; t += k; Serial.println(t);
Serial.println(map(50, 0, 100, 0, 255));
Serial.println(7 % 3);
Serial.println(1 << 4);
bool b = 5; Serial.println(b);
Serial.print(255, HEX); Serial.println();
uint8_t teinte = 255; uint8_t avant = teinte++; Serial.println(String(avant) + "/" + String(teinte));
const int NOTES[] = {659, 587};
Serial.println(NOTES[1]);
unsigned long t0 = millis(); delay(1500); Serial.println(millis() - t0);
while (millis() < 4000) { }
Serial.println("fin");
while (true) { delay(100); }
"""


@needs_node
def test_c_semantics_in_javascript(tmp_path):
    spec = ProjectSpec(title="sémantique", board="esp32-devkit-v1", parts=[], logic=SEMANTICS)
    out = run(simulation_payload(CAT, spec), tmp_path, until=6_000)
    lines = out["serial"].splitlines()
    assert lines == [
        "4", "3", "-3", "3.50", "3.142", "4294967295", "-128", "xA", "127", "1", "16", "1", "FF",
        "255/0", "587", "1500", "fin",
    ]  # fmt: skip


@needs_node
@pytest.mark.parametrize("tid", sorted(CAT.templates))
def test_every_template_runs_two_virtual_minutes(tid, tmp_path):
    """Chaque projet tourne 120 s virtuelles, capteurs bougés, sans erreur ; tous ses composants sont modélisés."""
    payload = simulation_payload(CAT, _spec(tid))
    out = run(payload, tmp_path, until=120_000, events=_stimuli(payload))
    assert out["error"] is None
    assert out["now"] >= 120_000
    unmodeled = [n for n, p in out["parts"].items() if not p["modeled"]]
    assert not unmodeled, unmodeled


# ---------------------------------------------------------------- scénarios
@needs_node
def test_door_alarm_rings_when_the_door_opens(tmp_path):
    payload = simulation_payload(CAT, _spec("alarme-porte"))
    porte = next(p["name"] for p in payload["parts"] if p["component"] == "reed-switch")
    out = run(
        payload,
        tmp_path,
        until=5_000,
        events=[
            [1_000, None, "mark", "ferme"],
            [2_000, porte, "set", "open", True],
            [3_000, None, "mark", "ouverte"],
        ],
    )
    assert out["sounds"] > 0
    assert not any(p["state"].get("on") for p in out["marks"]["ferme"]["parts"].values())
    assert any(p["state"].get("on") for p in out["marks"]["ouverte"]["parts"].values())


@needs_node
def test_thermostat_heats_below_the_setpoint(tmp_path):
    payload = simulation_payload(CAT, _spec("thermostat-relais"))
    out = run(
        payload,
        tmp_path,
        until=8_000,
        events=[
            [500, "sonde", "set", "temperature", 18],
            [2_500, None, "mark", "froid"],
            [3_000, "sonde", "set", "temperature", 23],
            [6_000, None, "mark", "chaud"],
        ],
    )
    froid, chaud = out["marks"]["froid"]["parts"], out["marks"]["chaud"]["parts"]
    assert (
        froid["chauffage"]["state"]["on"] is True and froid["afficheur"]["state"]["text"] == " 180"
    )
    assert chaud["chauffage"]["state"]["on"] is False


@needs_node
def test_keypad_code_opens_the_strike(tmp_path):
    payload = simulation_payload(CAT, _spec("digicode"))
    keys = [[1_000 + 300 * i, "clavier", "fire", "key", k] for i, k in enumerate("1234#")]
    out = run(payload, tmp_path, until=5_000, events=[*keys, [3_000, None, "mark", "ouvert"]])
    assert out["marks"]["ouvert"]["parts"]["gache"]["state"]["on"] is True
    assert out["parts"]["gache"]["state"]["on"] is False  # refermée après 3 s


@needs_node
def test_line_follower_turns_towards_the_line(tmp_path):
    payload = simulation_payload(CAT, _spec("robot-suiveur-ligne"))
    out = run(payload, tmp_path, until=2_000, events=[[500, "gauche", "set", "line", True]])
    assert out["loads"] == {"roue_gauche": 40, "roue_droite": 190}


@needs_node
def test_weather_web_page_is_served_on_request(tmp_path):
    payload = simulation_payload(CAT, _spec("station-meteo-web"))
    out = run(payload, tmp_path, until=3_000, events=[[1_000, None, "request", None]])
    assert "Temperature : 22.0" in out["web"]["body"]
    assert "192.168.1.42" in out["serial"]


@needs_node
def test_hourglass_ring_empties_over_time(tmp_path):
    payload = simulation_payload(CAT, _spec("sablier-lumineux"))
    out = run(
        payload,
        tmp_path,
        until=20_000,
        events=[
            [100, "potar", "set", "position", 0],
            [500, "bouton", "press", "pressed"],
            [600, "bouton", "release", "pressed"],
            [15_500, None, "mark", "moitie"],
        ],
    )
    lit = sum(1 for px in out["marks"]["moitie"]["parts"]["anneau"]["state"]["pixels"] if any(px))
    assert 5 <= lit <= 7  # 30 s de sablier, 15 s écoulées : la moitié des 12 LED


@needs_node
def test_reaction_game_busy_wait_advances_virtual_time(tmp_path):
    payload = simulation_payload(CAT, _spec("jeu-reflexes"))
    out = run(payload, tmp_path, until=10_000)
    assert "Temps de reaction : 3000 ms" in out["serial"]
