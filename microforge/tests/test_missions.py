"""Missions de l'atelier : données cohérentes, et chaque mission réussit avec son action, échoue sans.

Le scénario « témoin » rejoue tout sauf l'action de la mission et arme la mission au même instant :
si le résultat attendu arrivait quand même, la mission serait gagnée sans rien faire (refusée ici).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from importlib import resources
from pathlib import Path
from typing import Any

import pytest
from microforge.core import get_catalog
from microforge.core.builder import ProjectBuilder
from microforge.core.ideas import load_path
from microforge.core.missions import (
    AUTOMATIQUES,
    Mission,
    charge_atelier,
    missions_du_modele,
    missions_ecrites,
)
from microforge.sim import simulation_payload

CAT = get_catalog()
BUILDER = ProjectBuilder(CAT)
RUNNER = Path(__file__).parent / "mission_runner.cjs"
STATIC = resources.files("microforge.sim").joinpath("static")
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node absent")
ECRITES = [(tid, m) for tid, missions in missions_ecrites().items() for m in missions]


def _spec(tid: str):
    board = "esp32-devkit-v1"
    if not CAT.template_fits(tid, CAT.boards[board]):
        board = CAT.boards_for_template(tid)[0].id
    return BUILDER.spec_from_template(tid, board)


def test_missions_ecrites_pour_le_parcours_et_coherentes():
    parcours = {tid for etape in load_path() for tid in etape.templates}
    for tid, missions in missions_ecrites().items():
        assert tid in CAT.templates, tid
        noms = {p.name for p in CAT.templates[tid].parts}
        for m in missions:
            assert m.parties() <= noms, (tid, m.id, m.parties() - noms)
            assert m.consigne.endswith((".", "!", "?", ")")), (tid, m.id)
    assert set(missions_ecrites()) <= parcours
    assert len(ECRITES) >= 50


def test_missions_automatiques_pour_tous_les_modeles():
    for tid in CAT.templates:
        ids = [m["id"] for m in charge_atelier(tid)]
        assert ids[:2] == ["brancher-sans-aide", "simulation-60s"]
    assert [m.id for m in missions_du_modele(None)] == [m.id for m in AUTOMATIQUES]
    assert "reglages_test" not in charge_atelier("alarme-porte")[2]


def test_mission_invalide_refusee():
    with pytest.raises(ValueError, match="action et attendu"):
        Mission(id="x", titre="x", consigne="x.")
    with pytest.raises(ValueError, match="opérateur"):
        Mission(
            id="x",
            titre="x",
            consigne="x.",
            action={"part": "a", "regle": "v", "op": "~", "valeur": 1},
            attendu={"serie": "a"},
        )
    assert Mission(id="x", titre="x", consigne="x.", auto="branchement").xp(3) == 5
    assert ECRITES[0][1].xp(2) == 20


def _evenements(action: dict[str, Any], t: int, reglages: dict[str, Any], fin: int) -> list[list]:
    """Ce que ferait l'utilisateur pour réaliser ``action`` à l'instant ``t``."""
    if "tous" in action:
        return [e for sous in action["tous"] for e in _evenements(sous, t, reglages, fin)]
    if "requete" in action:
        return [[t, None, "request", action["requete"], None]]
    if "regle" in action:
        return [[t, action["part"], "set", action["regle"], action.get("essai", action["valeur"])]]
    if "appui" in action:
        repete = reglages.get("repete_ms")
        instants = (
            range(t, fin, repete) if repete else [t + 400 * i for i in range(action.get("fois", 1))]
        )
        return [
            e
            for i in instants
            for e in (
                [i, action["part"], "press", action["appui"], None],
                [i + 50, action["part"], "release", action["appui"], None],
            )
        ]
    if "evenement" in action:
        return [[t, action["part"], "fire", action["evenement"], action["valeur"]]]
    raise AssertionError(f"action inconnue : {action}")


def _scenario(tid: str, mission: Mission, temoin: bool) -> dict[str, Any]:
    """Actions des missions préalables (« apres »), puis celle de la mission (ou rien, pour le témoin)."""
    precedentes = {m.id: m for m in missions_ecrites()[tid]}
    chaine, courante = [], mission
    while courante.apres:
        courante = precedentes[courante.apres]
        chaine.insert(0, courante)
    t = mission.reglages_test.get("test_ms", 2000)
    fin = t + mission.fenetre_ms + 1000
    events = []
    for prealable in chaine:
        tp = prealable.reglages_test.get("test_ms", 2000)
        events += _evenements(
            prealable.action, tp, prealable.reglages_test, tp + prealable.fenetre_ms
        )
    if temoin:
        armer = [[t, mission.id]]
    else:
        events += _evenements(mission.action, t, mission.reglages_test, fin)
        armer = []
    return {"until": fin, "events": events, "armer": armer}


def _jouer(payload: dict, scenario: dict, tmp_path: Path) -> dict:
    (tmp_path / "payload.json").write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "scenario.json").write_text(json.dumps(scenario), encoding="utf-8")
    proc = subprocess.run(
        ["node", str(RUNNER), str(STATIC / "mfsim.js"), str(STATIC / "missions.js"),
         str(tmp_path / "payload.json"), str(tmp_path / "scenario.json")],
        capture_output=True, text=True, timeout=120, check=False,
    )  # fmt: skip
    assert proc.returncode == 0, proc.stderr[-2000:]
    sortie = json.loads(proc.stdout)
    assert sortie["erreur"] is None, sortie["erreur"]
    return sortie


@needs_node
@pytest.mark.parametrize(("tid", "mission"), ECRITES, ids=[f"{t}/{m.id}" for t, m in ECRITES])
def test_mission_reussie_avec_son_action_et_pas_sans(tid, mission, tmp_path):
    payload = simulation_payload(CAT, _spec(tid))
    avec = _jouer(payload, _scenario(tid, mission, temoin=False), tmp_path)
    assert mission.id in avec["reussies"], f"{tid}/{mission.id} : jamais réussie avec son action"
    sans = _jouer(payload, _scenario(tid, mission, temoin=True), tmp_path)
    assert mission.id not in sans["reussies"], (
        f"{tid}/{mission.id} : réussie sans l'action de l'utilisateur"
    )


@needs_node
def test_missions_automatiques(tmp_path):
    payload = simulation_payload(CAT, _spec("alarme-porte"))
    ok = _jouer(payload, {"until": 61_000, "events": []}, tmp_path)
    assert {"brancher-sans-aide", "simulation-60s"} <= set(ok["reussies"])
    assert ok["instants"]["simulation-60s"] >= 60_000
    aide = _jouer(payload, {"until": 61_000, "events": [], "aide": True}, tmp_path)
    assert "brancher-sans-aide" not in aide["reussies"] and "simulation-60s" in aide["reussies"]
    debranche = _jouer(payload, {"until": 61_000, "events": [], "branche": False}, tmp_path)
    assert debranche["reussies"] == []


@needs_node
def test_mission_dependante_attend_la_precedente(tmp_path):
    payload = simulation_payload(CAT, _spec("alarme-porte"))
    # Porte ouverte puis refermée, sans que « ouvrir » soit réussie d'abord (montage débranché au début).
    scenario = {
        "until": 8000,
        "events": [[2000, "porte", "set", "open", True], [4000, "porte", "set", "open", False]],
    }
    sortie = _jouer(payload, scenario, tmp_path)
    assert {"ouvrir", "refermer"} <= set(sortie["reussies"])
    assert sortie["instants"]["ouvrir"] < sortie["instants"]["refermer"]
