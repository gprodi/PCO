"""Infrastructure : isolement réseau du compose, image non root, configuration versionnée."""

import tomllib

import yaml

from tests.faux import RACINE

COMPOSE = yaml.safe_load((RACINE / "docker-compose.yml").read_text(encoding="utf-8"))
SERVICES = COMPOSE["services"]


def test_bases_et_api_de_donnees_inaccessibles_de_l_exterieur():
    assert COMPOSE["networks"]["prive"]["internal"] is True
    for nom in ("db", "vecteurs", "api_data"):
        assert SERVICES[nom]["networks"] == ["prive"] and "ports" not in SERVICES[nom]
    assert set(SERVICES["api_ia"]["networks"]) == {"prive", "public"}  # seule passerelle
    assert SERVICES["ui"]["networks"] == ["public"]


def test_secrets_lus_dans_l_environnement():
    texte = (RACINE / "docker-compose.yml").read_text(encoding="utf-8")
    assert "${POSTGRES_PASSWORD:?" in texte
    exemple = (RACINE / ".env.example").read_text(encoding="utf-8")
    for ligne in exemple.splitlines():
        if ligne.startswith(("APP_SECRET_KEY", "APP_DATA_API_KEY", "POSTGRES_PASSWORD")):
            assert ligne.endswith("="), f"valeur secrète dans .env.example : {ligne}"


def test_image_sans_root_et_theme_versionne():
    dockerfile = (RACINE / "Dockerfile").read_text(encoding="utf-8")
    assert "USER app" in dockerfile
    theme = tomllib.loads((RACINE / ".streamlit/config.toml").read_text(encoding="utf-8"))
    assert theme["theme"]["base"] == "dark" and theme["browser"]["gatherUsageStats"] is False


def test_supervision_coherente_avec_les_metriques():
    import json
    import re

    import pytest

    dossier = RACINE / "supervision"
    if not dossier.exists():
        pytest.skip("supervision non générée")
    declarees = set(re.findall(r'"(assistant_[a-z_]+)"', (RACINE / "api_ia/metriques.py").read_text(encoding="utf-8")))
    regles = yaml.safe_load((dossier / "prometheus/alertes.yml").read_text(encoding="utf-8"))
    expressions = [r["expr"] for g in regles["groups"] for r in g["rules"]]
    tableau = json.loads((dossier / "grafana/dashboards/assistant.json").read_text(encoding="utf-8"))
    expressions += [c["expr"] for p in tableau["panels"] for c in p["targets"]]
    for expression in expressions:
        for nom in re.findall(r"assistant_[a-z_]+", expression):
            assert re.sub(r"_(bucket|sum|count)$", "", nom) in declarees, nom
    assert {"api_ia:8001", "api_data:8000"} <= {
        cible for job in yaml.safe_load((dossier / "prometheus/prometheus.yml").read_text())["scrape_configs"]
        for config in job["static_configs"] for cible in config["targets"]
    }  # fmt: skip
