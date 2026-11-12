"""Onglet « Apprendre » : explications complètes et justes, glossaire utile, quiz cohérents."""

from __future__ import annotations

import re

import pytest
from microforge.core import get_catalog
from microforge.core.builder import ProjectBuilder
from microforge.core.ideas import load_path
from microforge.core.models import SignalRole
from microforge.core.pedagogie import (
    api_doc,
    apprendre,
    expliquer_ligne,
    glossaire,
    montage,
    notions,
    quiz,
)

CAT = get_catalog()
BUILDER = ProjectBuilder(CAT)


def _build(tid: str, board: str = "esp32-devkit-v1"):
    if not CAT.template_fits(tid, CAT.boards[board]):
        board = CAT.boards_for_template(tid)[0].id
    return BUILDER.build(BUILDER.spec_from_template(tid, board))


def _appels() -> set[tuple[str, str]]:
    """(composant, fonction) de chaque appel écrit dans la logique des 145 modèles."""
    paires = set()
    for t in CAT.templates.values():
        code = "\n".join([t.globals_extra, t.setup_extra, t.logic])
        for p in t.parts:
            for fn in re.findall(rf"\b{re.escape(p.name)}_([a-z_0-9]+)\s*\(", code):
                paires.add((p.component, fn))
    return paires


def test_chaque_fonction_utilisee_a_son_explication():
    doc = api_doc()
    manquantes = sorted(
        (comp, fn)
        for comp, fn in _appels()
        if fn not in doc["fonctions"] and fn not in doc["composants"].get(comp, {})
    )
    assert manquantes == []
    for texte in [
        *doc["fonctions"].values(),
        *(t for c in doc["composants"].values() for t in c.values()),
    ]:
        assert "{nom}" in texte or texte, texte
    assert set(doc["composants"]) <= set(CAT.components), set(doc["composants"]) - set(
        CAT.components
    )


def test_explication_d_une_ligne():
    notes = expliquer_ligne(
        "  if (porte_open()) { sirene_beep(2200, 150); delay(300); }",
        {"porte": "reed-switch", "sirene": "buzzer"},
    )
    assert notes[0].startswith("porte_open() : vrai si le contact « porte » est ouvert")
    assert any(n.startswith("sirene_beep() : fait sonner « sirene »") for n in notes)
    assert any(n.startswith("delay() :") for n in notes)
    # précision par composant : « on » d'un relais n'est pas « on » d'une LED
    relais = expliquer_ligne("lampe_on();", {"lampe": "relay-module-1ch"})
    assert "ferme le relais" in relais[0]


@pytest.mark.parametrize(
    "tid", ["alarme-porte", "station-meteo-oled", "thermostat-relais", "robot-evitement"]
)
def test_montage_masses_puis_alimentations_puis_signaux(tid):
    r = _build(tid)
    etapes = montage(r, CAT)
    assert len(etapes) == len(r.assignments)
    rangs = [0 if e["role"] == "ground" else 1 if e["role"] == "power" else 2 for e in etapes]
    assert rangs == sorted(rangs)
    for e in etapes:
        assert (e["pourquoi"].endswith(".") and e["vers"] in e["pourquoi"]) or e["role"] == "ground"
        assert "3.3" not in e["pourquoi"].split("résistance")[0]  # nombres à la française


def test_pourquoi_cite_l_adc1_le_bus_i2c_et_la_resistance():
    station = apprendre(_build("station-meteo-oled"), CAT)
    i2c = [e for e in station["montage"] if e["role"] == "i2c_sda"]
    assert i2c and "Bus I2C" in i2c[0]["pourquoi"] and "0x3C" in i2c[0]["pourquoi"]
    alarme = apprendre(_build("alarme-porte"), CAT)
    led = next(e for e in alarme["montage"] if e["part"] == "voyant" and e["role"] == "gpio_out")
    assert "résistance de 150 Ω" in led["pourquoi"]
    veilleuse = _build("veilleuse-auto")
    analogique = [a for a in veilleuse.assignments if a.role == SignalRole.ADC]
    if analogique and veilleuse.board.adc2_wifi_conflict:
        texte = next(e for e in montage(veilleuse, CAT) if e["role"] == "adc")["pourquoi"]
        assert "ADC1" in texte


def test_code_explique_chaque_fonction_une_fois():
    lignes = apprendre(_build("alarme-porte"), CAT)["code"]
    notes = [n.split(" : ", 1)[0] for ligne in lignes for n in ligne["notes"]]
    assert len(notes) == len(set(notes)) and "delay()" in notes and "porte_open()" in notes


def test_notions_du_glossaire():
    termes = {e["terme"] for e in glossaire()}
    assert len(termes) == len(glossaire()) >= 35
    for e in glossaire():
        assert e["definition"].endswith(".") and len(e["definition"]) > 30
    station = {n["terme"] for n in notions(_build("station-meteo-oled"), CAT)}
    assert "Bus I2C" in station
    thermostat = {n["terme"] for n in notions(_build("thermostat-relais"), CAT)}
    assert {"Hystérésis", "Bus 1-Wire"} <= thermostat
    sans_notion = [tid for tid in CAT.templates if not notions(_build(tid), CAT)]
    assert len(sans_notion) <= 5, sans_notion  # presque tous les projets ont au moins une notion


def test_quiz_coherents():
    etapes = {s.etape for s in load_path()}
    assert set(quiz()) == etapes
    for n, questions in quiz().items():
        assert len(questions) == 6, n
        for q in questions:
            assert 3 <= len(q["choix"]) <= 4 and len(set(q["choix"])) == len(q["choix"])
            assert 0 <= q["bonne"] < len(q["choix"]) and q["explication"].endswith(".")
    assert apprendre(_build("alarme-porte"), CAT)["quiz"]["etape"] == 2
    assert apprendre(_build("pate-qui-leve"), CAT)["quiz"] is None  # hors parcours
