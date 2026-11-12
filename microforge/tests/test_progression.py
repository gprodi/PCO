"""Progression : missions réussies enregistrées, points, niveau, badges, parcours, RGPD."""

from __future__ import annotations

from conftest import register_and_login
from microforge.core import get_catalog
from microforge.core.ideas import load_path
from microforge.core.missions import missions_ecrites
from microforge.core.progression import badges, bilan, niveau

CAT = get_catalog()


def auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_bilan_vide_puis_points_niveau_et_badges():
    vide = bilan([], CAT)
    assert (
        vide["xp"] == 0
        and vide["niveau"]["nom"] == "Apprenti"
        and vide["niveau"]["prochain"] == "Bricoleur"
    )
    assert not any(b["obtenu"] for b in vide["badges"])
    assert vide["prochaine"] == {
        "template_id": "feu-tricolore-pieton",
        "mission_id": "appel-pieton",
    }
    assert [e["etape"] for e in vide["etapes"]] == [s.etape for s in load_path()]

    difficulte = CAT.templates["alarme-porte"].difficulty
    b = bilan(
        [("alarme-porte", "ouvrir"), ("alarme-porte", "brancher-sans-aide"), ("inconnu", "x")], CAT
    )
    assert (
        b["xp"] == 10 * difficulte + 5
    )  # mission écrite + mission automatique ; l'inconnue est ignorée
    obtenus = {x["id"] for x in b["badges"] if x["obtenu"]}
    assert obtenus == {"premier-pas"}


def test_badge_d_etape_et_cableur():
    etape1 = next(s for s in load_path() if s.etape == 1)
    toutes = [(t, m.id) for t in etape1.templates for m in missions_ecrites().get(t, ())]
    cablages = [(t, "brancher-sans-aide") for t in list(CAT.templates)[:3]]
    b = bilan(toutes + cablages, CAT)
    obtenus = {x["id"] for x in b["badges"] if x["obtenu"]}
    assert {"etape-1", "cableur", "premier-pas"} <= obtenus and "etape-2" not in obtenus
    e1 = next(e for e in b["etapes"] if e["etape"] == 1)
    assert e1["faites"] == e1["total"] == len(toutes) and e1["prochaine"] is None
    assert b["prochaine"]["template_id"] in next(s for s in load_path() if s.etape == 2).templates


def test_niveaux_et_regles_de_badges():
    assert niveau(99)["nom"] == "Apprenti" and niveau(100)["nom"] == "Bricoleur"
    assert niveau(5000) == {
        "nom": "Ingénieur",
        "xp_niveau": 1500,
        "prochain": None,
        "xp_prochain": None,
    }
    regles = {k for b in badges() for k in b["regle"]}
    assert regles <= {"missions", "mission", "projets", "etape", "themes", "xp"}
    assert {b["id"] for b in badges()} >= {f"etape-{s.etape}" for s in load_path()}


def test_api_enregistre_une_fois_et_refuse_l_inconnu(data_client):
    h = auth(register_and_login(data_client, "joueur"))
    assert data_client.get("/v1/progression").status_code == 401
    assert data_client.get("/v1/progression", headers=h).json()["xp"] == 0
    corps = {"template_id": "alarme-porte", "mission_id": "ouvrir"}
    premiere = data_client.post("/v1/progression", json=corps, headers=h)
    assert premiere.status_code == 201 and premiere.json()["xp"] > 0
    encore = data_client.post("/v1/progression", json=corps, headers=h)
    assert encore.status_code == 200 and encore.json()["missions"] == premiere.json()["missions"]
    assert (
        data_client.post(
            "/v1/progression",
            json={"template_id": "alarme-porte", "mission_id": "voler"},
            headers=h,
        ).status_code
        == 404
    )
    assert (
        data_client.post(
            "/v1/progression",
            json={"template_id": "pas-un-modele", "mission_id": "ouvrir"},
            headers=h,
        ).status_code
        == 404
    )
    assert (
        data_client.post(
            "/v1/progression", json={"template_id": "../x", "mission_id": "ouvrir"}, headers=h
        ).status_code
        == 422
    )
    # chacun sa progression
    autre = auth(register_and_login(data_client, "autre"))
    assert data_client.get("/v1/progression", headers=autre).json()["missions"] == []


def test_progression_exportee_puis_effacee_avec_le_compte(data_client):
    h = auth(register_and_login(data_client, "rgpd", email="rgpd@example.org"))
    data_client.post(
        "/v1/progression", json={"template_id": "lampe-tactile", "mission_id": "allumer"}, headers=h
    )
    export = data_client.get("/v1/users/me/export", headers=h).json()
    assert [(m["template_id"], m["mission_id"]) for m in export["missions_reussies"]] == [
        ("lampe-tactile", "allumer")
    ]
    assert data_client.delete("/v1/users/me", headers=h).status_code == 204
    from microforge.api_data.db import MissionReussie, get_engine
    from sqlmodel import Session, select

    with Session(get_engine()) as s:
        assert s.exec(select(MissionReussie)).all() == []
