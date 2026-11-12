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


def run(
    payload: dict,
    tmp_path: Path,
    until: int = 60_000,
    events: list | None = None,
    start: str | None = None,
) -> dict:
    """Simulation dans Node ; ``start`` : date et heure de départ de l'horloge (8 h le 03/11/2026)."""
    (tmp_path / "payload.json").write_text(json.dumps(payload), encoding="utf-8")
    scenario = {"until": until, "events": events or []} | ({"startDate": start} if start else {})
    (tmp_path / "scenario.json").write_text(json.dumps(scenario))
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


# ---------------------------------------------------------------- thème « Animaux »
@needs_node
def test_feeder_opens_once_at_meal_time(tmp_path):
    """La simulation démarre à 8 h 00 : une portion, une seule, pour ce repas."""
    out = run(
        simulation_payload(CAT, _spec("distributeur-croquettes")),
        tmp_path,
        until=8_000,
        events=[[500, None, "mark", "repas"], [3_000, None, "mark", "apres"]],
    )
    assert out["marks"]["repas"]["parts"]["trappe"]["state"]["angle"] == 90
    assert out["marks"]["apres"]["parts"]["trappe"]["state"]["angle"] == 0
    assert out["parts"]["trappe"]["state"]["angle"] == 0
    assert out["serial"].count("Repas servi") == 1


@needs_node
def test_aquarium_heats_below_the_setpoint_and_stops_without_probe(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("surveillance-aquarium")),
        tmp_path,
        until=6_000,
        events=[
            [200, "sonde", "set", "temperature", 22],
            [2_000, None, "mark", "froid"],
            [2_500, "sonde", "set", "temperature", 27],
            [4_500, None, "mark", "chaud"],
        ],
    )
    assert out["marks"]["froid"]["parts"]["chauffage"]["state"]["on"] is True
    assert out["marks"]["chaud"]["parts"]["chauffage"]["state"]["on"] is False


@needs_node
def test_cat_flap_opens_only_for_the_cat_tag(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("chatiere-badge")),
        tmp_path,
        until=12_000,
        events=[
            [500, "lecteur", "fire", "badge", "12 34 56 78"],
            [1_500, None, "mark", "voisin"],
            [2_000, "lecteur", "fire", "badge", "DE AD BE EF"],
            [3_500, None, "mark", "chat"],
        ],
    )
    assert out["marks"]["voisin"]["parts"]["verrou"]["state"]["angle"] == 0
    assert out["marks"]["chat"]["parts"]["verrou"]["state"]["angle"] == 90
    assert out["parts"]["verrou"]["state"]["angle"] == 0  # refermée après 5 s


@needs_node
def test_hamster_passages_are_counted_once_each(tmp_path):
    events = []
    for t0 in (1_000, 5_000, 9_000):
        events += [[t0, "detecteur", "press", "pass"], [t0 + 1_500, "detecteur", "release", "pass"]]
    out = run(simulation_payload(CAT, _spec("compteur-hamster")), tmp_path, 12_000, events)
    assert out["parts"]["afficheur"]["state"]["text"] == "   3"


@needs_node
def test_water_bowl_blinks_when_empty(tmp_path):
    marks = [[1_000 + 150 * i, None, "mark", f"m{i}"] for i in range(6)]
    out = run(
        simulation_payload(CAT, _spec("gamelle-eau")),
        tmp_path,
        until=3_000,
        events=[[100, "niveau", "set", "level", 0], *marks],
    )
    states = {out["marks"][f"m{i}"]["parts"]["voyant"]["state"]["on"] for i in range(6)}
    # Elle clignote. Ce test a révélé un défaut du simulateur : un évènement pendant delay()
    # en repoussait la fin, et des relevés rapprochés étaient tous pris dans la même attente.
    assert states == {True, False}
    out = run(
        simulation_payload(CAT, _spec("gamelle-eau")),
        tmp_path,
        until=3_000,
        events=[[100, "niveau", "set", "level", 80]],
    )
    assert out["parts"]["voyant"]["state"]["on"] is False


# ---------------------------------------------------------------- thème « Musique & son »
@needs_node
def test_piano_plays_the_held_key(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("piano-boutons")),
        tmp_path,
        until=2_000,
        events=[
            [500, "touche_mi", "press", "pressed"],
            [700, None, "mark", "mi"],
            [900, "touche_mi", "release", "pressed"],
        ],
    )
    assert out["marks"]["mi"]["parts"]["hp"]["state"]["freq"] == 330


@needs_node
def test_theremin_pitch_rises_as_the_hand_gets_closer(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("theremine-ultrasons")),
        tmp_path,
        until=3_000,
        events=[
            [200, "main", "set", "distance", 40],
            [800, None, "mark", "loin"],
            [1_000, "main", "set", "distance", 10],
            [1_600, None, "mark", "pres"],
        ],
    )
    loin = out["marks"]["loin"]["parts"]["hp"]["state"]["freq"]
    pres = out["marks"]["pres"]["parts"]["hp"]["state"]["freq"]
    assert 200 <= loin < pres <= 1500


@needs_node
def test_metronome_tempo_follows_the_potentiometer(tmp_path):
    lent = run(
        simulation_payload(CAT, _spec("metronome")),
        tmp_path,
        until=6_000,
        events=[[0, "tempo", "set", "position", 0]],
    )
    rapide = run(
        simulation_payload(CAT, _spec("metronome")),
        tmp_path,
        until=6_000,
        events=[[0, "tempo", "set", "position", 100]],
    )
    assert 3 <= lent["sounds"] <= 5  # 40 BPM : un temps toutes les 1,5 s
    assert 20 <= rapide["sounds"] <= 22  # 208 BPM : un temps toutes les 0,29 s


@needs_node
def test_music_box_plays_a_whole_tune_per_badge(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("boite-musique-badge")),
        tmp_path,
        until=8_000,
        events=[[300, "lecteur", "fire", "badge", "DE AD BE EF"]],
    )
    assert out["sounds"] == 11  # Au clair de la lune : 11 notes


@needs_node
def test_sound_meter_waits_two_seconds_before_the_sad_face(tmp_path):
    """Régression : le repère « millis() + 1 » rendait millis() - debut négatif, donc énorme en
    non signé, et la tête triste apparaissait dès le premier bruit fort."""
    out = run(
        simulation_payload(CAT, _spec("sonometre-classe")),
        tmp_path,
        until=4_000,
        events=[
            [100, "micro", "set", "level", 95],
            [1_000, None, "mark", "bruit"],
        ],
    )
    assert out["marks"]["bruit"]["parts"]["matrice"]["state"]["rows"] == [0xFF] * 8
    assert out["parts"]["matrice"]["state"]["rows"][2] == 0xA5  # tête triste après 2 s


@needs_node
def test_sound_meter_bars_follow_the_level(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("sonometre-classe")),
        tmp_path,
        until=2_000,
        events=[[100, "micro", "set", "level", 50]],
    )
    assert out["parts"]["matrice"]["state"]["rows"][0] == 0xF8  # 5 colonnes sur 8


# ---------------------------------------------------------------- thème « Fêtes & déco »
def _lit(part: dict) -> int:
    return sum(1 for px in part["state"]["pixels"] if any(px))


@needs_node
def test_pumpkin_screams_when_someone_passes(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("citrouille-halloween")),
        tmp_path,
        until=3_000,
        events=[
            [200, None, "mark", "calme"],
            [500, "detecteur", "press", "pass"],
            [700, None, "mark", "cri"],
            [800, "detecteur", "release", "pass"],
        ],
    )
    assert not out["marks"]["calme"]["parts"]["oeil_g"]["state"]["on"]
    assert 300 <= out["marks"]["cri"]["parts"]["cri"]["state"]["freq"] <= 1500
    assert out["sounds"] >= 10


@needs_node
@pytest.mark.parametrize(("start", "lit"), [("2026-11-03T08:00:00", 0), ("2026-12-12T08:00:00", 6)])
def test_advent_wreath_fills_up_in_december(tmp_path, start, lit):
    payload = simulation_payload(CAT, _spec("calendrier-avent"))
    out = run(payload, tmp_path, until=2_000, start=start)
    assert _lit(out["parts"]["couronne"]) == lit


@needs_node
@pytest.mark.parametrize(
    ("start", "text"),
    [
        ("2026-11-03T08:00:00", "  59"),
        ("2026-12-30T08:00:00", "   2"),
        ("2026-12-31T22:30:00", "0129"),
    ],
)
def test_new_year_countdown(tmp_path, start, text):
    out = run(
        simulation_payload(CAT, _spec("compte-a-rebours-nouvel-an")), tmp_path, 2_000, start=start
    )
    assert out["parts"]["afficheur"]["state"]["text"] == text


@needs_node
def test_new_year_fireworks_at_midnight(tmp_path):
    payload = simulation_payload(CAT, _spec("compte-a-rebours-nouvel-an"))
    out = run(payload, tmp_path, until=3_000, start="2027-01-01T00:00:00")
    assert out["sounds"] >= 10


@needs_node
def test_birthday_candles_go_out_three_at_a_time(tmp_path):
    claps = []
    for t0 in (500, 1_500):
        claps += [[t0, "micro", "press", "clap"], [t0 + 50, "micro", "release", "clap"]]
    out = run(
        simulation_payload(CAT, _spec("gateau-anniversaire")),
        tmp_path,
        until=3_000,
        events=claps,
    )
    assert _lit(out["parts"]["bougies_led"]) == 6
    assert "Bougies allumées : 6" in out["serial"]


@needs_node
def test_surprise_box_plays_a_fanfare_when_opened(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("boite-surprise")),
        tmp_path,
        until=3_000,
        events=[
            [500, "couvercle", "set", "open", True],
            [1_500, None, "mark", "ouverte"],
            [2_000, "couvercle", "set", "open", False],
        ],
    )
    assert out["sounds"] == 4  # do mi sol do, une seule fois
    assert _lit(out["marks"]["ouverte"]["parts"]["anneau"]) == 12
    assert _lit(out["parts"]["anneau"]) == 0


# ---------------------------------------------------------------- thème « Cuisine »
@needs_node
def test_kitchen_timer_counts_down_and_rings(tmp_path):
    turns = [[200 + 50 * i, "molette", "fire", "turn", "-1"] for i in range(4)]  # 5 → 1 min
    out = run(
        simulation_payload(CAT, _spec("minuteur-cuisine")),
        tmp_path,
        until=64_000,
        events=[
            *turns,
            [600, None, "mark", "regle"],
            [1_000, "molette", "press", "sw"],
            [1_100, "molette", "release", "sw"],
            [31_500, None, "mark", "moitie"],
        ],
    )
    assert out["marks"]["regle"]["parts"]["afficheur"]["state"]["text"] == "0100"
    assert out["marks"]["moitie"]["parts"]["afficheur"]["state"]["text"] in {"0029", "0030", "0031"}
    assert "C'est prêt !" in out["serial"] and out["sounds"] > 0


@needs_node
def test_cooking_thermometer_rings_at_the_target(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("thermometre-cuisson")),
        tmp_path,
        until=6_000,
        events=[
            [100, "sonde", "set", "temperature", 40],
            [1_500, None, "mark", "froid"],
            [2_000, "sonde", "set", "temperature", 65],
        ],
    )
    assert out["marks"]["froid"]["parts"]["afficheur"]["state"]["text"] == "  40"
    assert out["marks"]["froid"]["parts"]["alarme"]["state"]["freq"] == 0
    assert out["parts"]["afficheur"]["state"]["text"] == "  65" and out["sounds"] > 0


@needs_node
def test_dough_rise_is_measured_from_the_start(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("pate-qui-leve")),
        tmp_path,
        until=12_000,
        events=[[2_000, "capteur", "set", "distance", 46]],  # départ à 50 cm : +4 cm
    )
    assert "100 %" in json.dumps(out["parts"]["ecran"]["state"], ensure_ascii=False)


@needs_node
def test_pan_overflow_alarm(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("alerte-casserole")),
        tmp_path,
        until=2_000,
        events=[[500, "niveau", "set", "level", 60]],
    )
    assert out["sounds"] > 0 and "déborde" in out["serial"]


# ---------------------------------------------------------------- thème « Plantes & jardin »
@needs_node
@pytest.mark.parametrize(
    ("moisture", "rgb"), [(10, [255, 0, 0]), (45, [255, 160, 0]), (80, [0, 255, 0])]
)
def test_soil_led_colour(tmp_path, moisture, rgb):
    out = run(
        simulation_payload(CAT, _spec("humidite-sol-led")),
        tmp_path,
        until=2_000,
        events=[[0, "sol", "set", "moisture", moisture]],
    )
    assert out["parts"]["voyant"]["state"]["rgb"] == rgb


@needs_node
def test_greenhouse_vents_when_hot_and_serves_its_page(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("serre-connectee")),
        tmp_path,
        until=6_000,
        events=[[0, "air", "set", "temperature", 30], [5_000, None, "request", None]],
    )
    assert out["parts"]["ventilation"]["state"]["on"] is True
    assert "Temperature : 30.0" in out["web"]["body"] and "Ventilation : oui" in out["web"]["body"]


@needs_node
@pytest.mark.parametrize(("temperature", "angle"), [(15, 0), (25, 45), (35, 90)])
def test_roof_vent_opens_with_the_heat(tmp_path, temperature, angle):
    out = run(
        simulation_payload(CAT, _spec("lucarne-automatique")),
        tmp_path,
        until=3_000,
        events=[[0, "sonde", "set", "temperature", temperature]],
    )
    assert out["parts"]["lucarne"]["state"]["angle"] == angle


@needs_node
def test_plant_light_meter(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("luxmetre-plantes")),
        tmp_path,
        until=2_000,
        events=[[0, "lumiere", "set", "light", 75]],
    )
    assert out["parts"]["afficheur"]["state"]["text"] == "  75"
    assert "Plein soleil" in out["serial"]


@needs_node
def test_compost_phase_and_maximum(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("thermometre-compost")),
        tmp_path,
        until=12_000,
        events=[[0, "sonde", "set", "temperature", 62], [6_000, "sonde", "set", "temperature", 40]],
    )
    ecran = json.dumps(out["parts"]["ecran"]["state"], ensure_ascii=False)
    assert "Mesophile" in ecran and "Max 62.0" in ecran


@needs_node
@pytest.mark.parametrize(("moisture", "beeps"), [(10, True), (80, False)])
def test_watering_reminder(tmp_path, moisture, beeps):
    out = run(
        simulation_payload(CAT, _spec("rappel-arrosage")),
        tmp_path,
        until=3_000,
        events=[[0, "sol", "set", "moisture", moisture]],
    )
    assert (out["sounds"] > 0) is beeps


@needs_node
@pytest.mark.parametrize(
    ("start", "lit"), [("2026-11-03T12:00:00", 12), ("2026-11-03T22:30:00", 0)]
)
def test_grow_light_schedule(tmp_path, start, lit):
    out = run(simulation_payload(CAT, _spec("lampe-croissance")), tmp_path, 2_000, start=start)
    assert _lit(out["parts"]["lampe"]) == lit


@needs_node
def test_rain_barrel_level(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("niveau-recuperateur")),
        tmp_path,
        until=3_000,
        events=[[0, "sonar", "set", "distance", 55]],  # (100 − 55) / 90 = 50 %
    )
    assert _lit(out["parts"]["jauge"]) == 6


# ---------------------------------------------------------------- « Domotique » et « Maison »
def _pass(part: str, t0: int, hold: int = 1_000) -> list:
    return [[t0, part, "press", "pass"], [t0 + hold, part, "release", "pass"]]


@needs_node
def test_light_turns_itself_off_a_minute_after_the_last_motion(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("lumiere-auto-pir")),
        tmp_path,
        until=75_000,
        events=[*_pass("detecteur", 500), [30_000, None, "mark", "allumee"]],
    )
    assert out["marks"]["allumee"]["parts"]["lampe"]["state"]["on"] is True
    assert out["parts"]["lampe"]["state"]["on"] is False


@needs_node
def test_blind_opens_at_dawn_and_closes_at_dusk(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("volet-roulant")),
        tmp_path,
        until=50_000,
        events=[
            [500, "capteur", "set", "light", 90],
            [20_000, None, "mark", "jour"],
            [21_000, "capteur", "set", "light", 10],
        ],
    )
    assert out["marks"]["jour"]["parts"]["moteur"]["state"]["position"] == 6144  # 3 tours
    assert out["parts"]["moteur"]["state"]["position"] == 0


@needs_node
@pytest.mark.parametrize(("light", "lit"), [(10, 12), (80, 0)])
def test_stairs_light_up_only_in_the_dark(tmp_path, light, lit):
    out = run(
        simulation_payload(CAT, _spec("escalier-automatique")),
        tmp_path,
        until=4_000,
        events=[[0, "luminosite", "set", "light", light], *_pass("detecteur", 500)],
    )
    assert _lit(out["parts"]["marches"]) == lit


@needs_node
def test_open_window_cuts_the_heating_after_30_s(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("fenetre-chauffage")),
        tmp_path,
        until=40_000,
        events=[[1_000, "fenetre", "set", "open", True], [10_000, None, "mark", "aeration"]],
    )
    assert out["marks"]["aeration"]["parts"]["chauffage"]["state"]["on"] is True
    assert out["parts"]["chauffage"]["state"]["on"] is False
    assert out["parts"]["voyant"]["state"]["on"] is True


@needs_node
def test_fridge_door_beeps_only_after_30_s(tmp_path):
    payload = simulation_payload(CAT, _spec("porte-frigo"))
    court = run(payload, tmp_path, 20_000, [[1_000, "porte", "set", "open", True]])
    long_ = run(payload, tmp_path, 40_000, [[1_000, "porte", "set", "open", True]])
    assert court["sounds"] == 0 and long_["sounds"] > 0


@needs_node
def test_dimmer_follows_the_knob(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("variateur-ruban")),
        tmp_path,
        until=1_000,
        events=[[0, "reglage", "set", "position", 40]],
    )
    assert out["parts"]["ruban"]["state"]["level"] == 102  # 40 % de 255


@needs_node
@pytest.mark.parametrize(
    ("humidity", "rgb"), [(50, [0, 255, 0]), (70, [255, 120, 0]), (85, [255, 0, 0])]
)
def test_bathroom_ventilation_indicator(tmp_path, humidity, rgb):
    out = run(
        simulation_payload(CAT, _spec("aeration-salle-de-bain")),
        tmp_path,
        until=6_000,
        events=[[0, "air", "set", "humidity", humidity]],
    )
    assert out["parts"]["voyant"]["state"]["rgb"] == rgb


@needs_node
@pytest.mark.parametrize(
    ("start", "lit"),
    [("2026-11-03T06:45:00", 12), ("2026-11-03T07:10:00", 12), ("2026-11-03T12:00:00", 0)],
)
def test_sunrise_alarm(tmp_path, start, lit):
    out = run(simulation_payload(CAT, _spec("reveil-lumineux")), tmp_path, 2_000, start=start)
    assert _lit(out["parts"]["anneau"]) == lit


@needs_node
def test_sunrise_alarm_button_switches_it_off_for_the_day(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("reveil-lumineux")),
        tmp_path,
        until=4_000,
        events=[[1_000, "bouton", "press", "pressed"], [1_100, "bouton", "release", "pressed"]],
        start="2026-11-03T07:10:00",
    )
    assert _lit(out["parts"]["anneau"]) == 0 and "Bonjour" in out["serial"]


@needs_node
@pytest.mark.parametrize(
    ("temperature", "humidity", "rgb"),
    [(21, 50, [0, 255, 0]), (27, 50, [255, 0, 0]), (16, 50, [0, 0, 255]), (21, 25, [255, 200, 0])],
)
def test_comfort_indicator(tmp_path, temperature, humidity, rgb):
    out = run(
        simulation_payload(CAT, _spec("indicateur-confort")),
        tmp_path,
        until=3_000,
        events=[
            [0, "capteur", "set", "temperature", temperature],
            [0, "capteur", "set", "humidity", humidity],
        ],
    )
    assert out["parts"]["voyant"]["state"]["rgb"] == rgb


@needs_node
def test_silent_doorbell_vibrates_three_times(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("sonnette-silencieuse")),
        tmp_path,
        until=4_000,
        events=[[500, "bouton", "press", "pressed"], [600, "bouton", "release", "pressed"]],
    )
    assert out["parts"]["vibreur"]["state"]["count"] == 3
    assert out["sounds"] == 0 and "On sonne ! (1)" in out["serial"]


# ---------------------------------------------------------------- « Extérieur » et « Sécurité »
@needs_node
def test_frost_alert_blinks_then_rings(tmp_path):
    marks = [[1_000 + 250 * i, None, "mark", f"m{i}"] for i in range(6)]
    risque = run(
        simulation_payload(CAT, _spec("alerte-gel")),
        tmp_path,
        until=3_000,
        events=[[0, "sonde", "set", "temperature", 2], *marks],
    )
    assert {risque["marks"][f"m{i}"]["parts"]["voyant"]["state"]["on"] for i in range(6)} == {
        True,
        False,
    }
    assert risque["sounds"] == 0
    gel = run(
        simulation_payload(CAT, _spec("alerte-gel")),
        tmp_path,
        until=3_000,
        events=[[0, "sonde", "set", "temperature", -2]],
    )
    assert gel["parts"]["voyant"]["state"]["on"] is True and gel["sounds"] == 1


@needs_node
@pytest.mark.parametrize(("light", "on"), [(5, True), (80, False)])
def test_garden_light_only_at_night(tmp_path, light, on):
    out = run(
        simulation_payload(CAT, _spec("eclairage-jardin")),
        tmp_path,
        until=3_000,
        events=[[0, "luminosite", "set", "light", light], *_pass("detecteur", 500)],
    )
    assert out["parts"]["eclairage"]["state"]["on"] is on


@needs_node
@pytest.mark.parametrize(
    ("pressure", "rgb"), [(1008, [255, 0, 0]), (1013.25, [255, 200, 0]), (1018, [0, 255, 0])]
)
def test_barometer_trend_over_the_hours(tmp_path, pressure, rgb):
    out = run(
        simulation_payload(CAT, _spec("barometre-prevision")),
        tmp_path,
        until=4_200_000,  # 70 minutes : 8 mesures
        events=[[2_400_000, "capteur", "set", "pressure", pressure]],
    )
    assert out["parts"]["voyant"]["state"]["rgb"] == rgb


@needs_node
def test_rain_alarm_for_the_washing(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("pluie-linge")),
        tmp_path,
        until=3_000,
        events=[[500, "gouttes", "set", "level", 60]],
    )
    assert out["sounds"] == 3 and "rentrer le linge" in out["serial"]


@needs_node
def test_balcony_lamp_lights_four_hours_after_dusk(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("lampe-solaire-balcon")),
        tmp_path,
        until=14_405_000,
        events=[[0, "luminosite", "set", "light", 5], [3_000, None, "mark", "soir"]],
    )
    assert _lit(out["marks"]["soir"]["parts"]["lampe"]) == 12
    assert _lit(out["parts"]["lampe"]) == 0 and "économie des piles" in out["serial"]


def _keys(part: str, t0: int, keys: str) -> list:
    return [[t0 + 100 * i, part, "fire", "key", k] for i, k in enumerate(keys)]


@needs_node
def test_safe_opens_with_the_code_and_locks_after_three_errors(tmp_path):
    payload = simulation_payload(CAT, _spec("coffre-code"))
    ok = run(payload, tmp_path, 2_000, _keys("clavier", 200, "2580#"))
    assert ok["parts"]["serrure"]["state"]["angle"] == 90 and ok["parts"]["voyant"]["state"]["on"]
    bloque = run(payload, tmp_path, 4_000, _keys("clavier", 200, "1#2#3#2580#"))
    assert bloque["parts"]["serrure"]["state"]["angle"] == 0
    assert "Clavier bloqué 30 s" in bloque["serial"]


@needs_node
def test_drawer_alarm_rings_when_light_gets_in(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("alarme-tiroir")),
        tmp_path,
        until=7_000,
        events=[[0, "lumiere", "set", "light", 0], [500, "lumiere", "set", "light", 60]],
    )
    assert out["sounds"] == 10


@needs_node
def test_bag_alarm_arms_triggers_and_disarms(tmp_path):
    out = run(
        simulation_payload(CAT, _spec("alarme-sac")),
        tmp_path,
        until=12_000,
        events=[
            [200, "bouton", "press", "pressed"],
            [300, "bouton", "release", "pressed"],
            [7_000, "mouvement", "set", "tx", 30],
            [8_000, None, "mark", "alarme"],
            [9_000, "bouton", "press", "pressed"],
            [9_100, "bouton", "release", "pressed"],
        ],
    )
    assert out["marks"]["alarme"]["parts"]["sirene"]["state"]["freq"] == 3000
    assert "Alarme : le sac a bougé" in out["serial"] and "Désarmée" in out["serial"]


@needs_node
def test_reaction_game_busy_wait_advances_virtual_time(tmp_path):
    payload = simulation_payload(CAT, _spec("jeu-reflexes"))
    out = run(payload, tmp_path, until=10_000)
    assert "Temps de reaction : 3000 ms" in out["serial"]


# ---------------------------------------------------------------- atelier : branchements et page
ATELIER_JS = resources.files("microforge.sim").joinpath("static/atelier.js")
CHECK_SCRIPT = """
const { checkPin } = require(process.argv[2]);
const p = JSON.parse(require("fs").readFileSync(process.argv[3], "utf8"));
const pin = (part, name) => p.wiring.pins.find((x) => x.part === part && x.pin === name);
const sup = (part) => p.parts.find((x) => x.name === part).supply;
const b = p.wiring.board;
console.log(JSON.stringify({
  ok: checkPin(pin("ecran", "SDA"), "D21", b, {}, sup("ecran")),
  i2c: checkPin(pin("ecran", "SDA"), "D22", b, {}, sup("ecran")),
  gnd: checkPin(pin("dht", "VCC"), "GND", b, {}, sup("dht")),
  vin: checkPin(pin("dht", "VCC"), "VIN", b, {}, sup("dht")),
  gpio: checkPin(pin("dht", "VCC"), "D26", b, {}, sup("dht")),
  inonly: checkPin(pin("dht", "DATA"), "D34", b, {}, sup("dht")),
  taken: checkPin(pin("dht", "DATA"), "D26", b, { D26: "led.A" }, sup("dht")),
  other: checkPin(pin("dht", "DATA"), "D26", b, {}, sup("dht")),
}));
"""


@needs_node
def test_wiring_mistakes_are_explained(tmp_path):
    from microforge.sim import atelier_payload

    result = BUILDER.build(BUILDER.spec_from_template("station-meteo-oled", "esp32-devkit-v1"))
    (tmp_path / "p.json").write_text(json.dumps(atelier_payload(CAT, result)), encoding="utf-8")
    (tmp_path / "check.cjs").write_text(CHECK_SCRIPT, encoding="utf-8")
    proc = subprocess.run(
        ["node", str(tmp_path / "check.cjs"), str(ATELIER_JS), str(tmp_path / "p.json")],
        capture_output=True,
        text=True,
        check=True,
    )
    r = json.loads(proc.stdout)
    assert r["ok"]["ok"] and not any(r[k]["ok"] for k in r if k != "ok")
    assert "I2C" in r["i2c"]["msg"] and "Court-circuit" in r["gnd"]["msg"]
    assert "entrées 3.3 V" in r["vin"]["msg"] and "quelques mA" in r["gpio"]["msg"]
    assert "entrée seule" in r["inonly"]["msg"] and "led.A" in r["taken"]["msg"]
    assert "généré pour D25" in r["other"]["msg"]


BROWSER_SCRIPT = """
const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.goto("file://" + process.argv[2]);
  await page.waitForFunction(() => window.atelier && window.atelier.sim);
  const before = await page.textContent(".mfa-count");
  await page.click("text=Tout brancher");
  await page.waitForFunction(() => document.querySelector(".mfa-serial").textContent.includes("22.00 C"));
  await page.evaluate(() => window.atelier.choose("ecran", "SDA", "D22"));
  const card = await page.$eval('[data-part="ecran"]', (c) => ({ unplugged: c.classList.contains("unplugged"), text: c.textContent }));
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  console.log(JSON.stringify({ before, after: await page.textContent(".mfa-count"), card, overflow, errors }));
  await browser.close();
})();
"""


def _has_playwright() -> bool:
    if shutil.which("node") is None:
        return False
    probe = subprocess.run(
        ["node", "-e", "require('playwright')"], capture_output=True, check=False
    )
    return probe.returncode == 0


@pytest.mark.skipif(not _has_playwright(), reason="Playwright (Node) absent")
def test_atelier_page_in_a_browser(tmp_path):
    """Page autonome sans Wokwi (dessins simples) : brancher, simuler, puis une erreur expliquée."""
    from microforge.sim import atelier_html, atelier_payload

    result = BUILDER.build(BUILDER.spec_from_template("station-meteo-oled", "esp32-devkit-v1"))
    html = tmp_path / "atelier.html"
    html.write_text(atelier_html(atelier_payload(CAT, result), wokwi_src=None), encoding="utf-8")
    (tmp_path / "b.cjs").write_text(BROWSER_SCRIPT, encoding="utf-8")
    proc = subprocess.run(
        ["node", str(tmp_path / "b.cjs"), str(html)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    r = json.loads(proc.stdout)
    assert r["errors"] == [] and not r["overflow"]
    assert "0/2" in r["before"] and "1/2" in r["after"]
    assert r["card"]["unplugged"] and "Le bus I2C par défaut" in r["card"]["text"]


def test_streamlit_atelier_page_renders():
    from streamlit.testing.v1 import AppTest

    page = Path(__file__).parents[1] / "src/microforge/app_streamlit/pages/7_Atelier.py"
    at = AppTest.from_file(str(page), default_timeout=60)
    at.run()
    assert not at.exception
    assert at.selectbox[0].value.id and at.selectbox[1].value.id
    at.selectbox[0].select(CAT.templates["digicode"]).run()
    assert not at.exception
    assert "__P.clavier.key()" in at.code[0].value
