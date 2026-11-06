"""Pile Docker locale (profil core) : elle démarre sans fichier .env.

Les valeurs de développement versionnées (microforge/.env.example) servent par défaut ; un fichier
microforge/.env, s'il existe, les remplace. Vérifié sans démon par ``docker compose config``, sur
une copie temporaire du compose : le vrai .env de l'utilisateur n'est jamais lu ni modifié.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

MF = Path(__file__).resolve().parents[1]
DOCKER = shutil.which("docker")


def _config(root: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("MF_")}
    proc = subprocess.run(
        [
            DOCKER,
            "compose",
            "-f",
            str(root / "infra" / "docker-compose.yml"),
            "--profile",
            "core",
            "config",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    return yaml.safe_load(proc.stdout)["services"]


@pytest.fixture
def copie(tmp_path) -> Path:
    if (
        DOCKER is None
        or subprocess.run([DOCKER, "compose", "version"], capture_output=True).returncode
    ):
        pytest.skip("Docker Compose absent")
    (tmp_path / "infra").mkdir()
    shutil.copy(MF / "infra" / "docker-compose.yml", tmp_path / "infra")
    shutil.copy(MF / ".env.example", tmp_path / ".env.example")
    for d in ("pwa", "infra/litellm"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_sans_env_les_services_se_trouvent(copie):
    services = _config(copie)
    db = "postgresql+psycopg://microforge:microforge@postgres:5432/microforge"
    assert services["api_data"]["environment"]["MF_DATABASE_URL"] == db
    assert services["api_ia"]["environment"]["MF_API_DATA_URL"] == "http://api_data:8000"
    assert services["streamlit"]["environment"]["MF_API_IA_URL"] == "http://api_ia:8001"
    # La PWA tourne dans le navigateur : elle appelle les API par les ports publiés.
    assert services["pwa"]["environment"]["MF_PUBLIC_API_DATA_URL"] == "http://localhost:8000"
    # Journaux JSON dans les conteneurs des API (Alloy en extrait le niveau pour Loki).
    for api in ("api_data", "api_ia"):
        assert services[api]["environment"]["MF_LOG_JSON"] == "true"


def test_le_fichier_env_remplace_les_valeurs_par_defaut(copie):
    (copie / ".env").write_text("MF_ENV=prod\nLLM_CHAIN=gemini\n", encoding="utf-8")
    env = _config(copie)["api_data"]["environment"]
    assert env["MF_ENV"] == "prod" and env["LLM_CHAIN"] == "gemini"
    assert env["MF_DATABASE_URL"].endswith("@postgres:5432/microforge")  # le reste garde le défaut


def _published(service: dict) -> list[str]:
    return [str(p["published"]) for p in service.get("ports", [])]


def test_ports_par_defaut(copie):
    services = _config(copie)
    assert _published(services["api_data"]) == ["8000"]
    assert _published(services["api_ia"]) == ["8001"]
    assert _published(services["pwa"]) == ["5173"]
    assert _published(services["streamlit"]) == ["8501"]
    cors = services["api_data"]["environment"]["MF_CORS_ORIGINS"].split(",")
    assert {"http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8501"} <= set(cors)


def test_port_deja_pris_sur_le_poste_se_change_dans_infra_env(copie):
    """Port 8000 occupé par un autre programme : MF_API_DATA_PORT=8010 dans infra/.env suffit, la PWA
    vise alors http://localhost:8010 et les origines CORS suivent le port de la PWA."""
    (copie / "infra" / ".env").write_text(
        "MF_API_DATA_PORT=8010\nMF_API_IA_PORT=8011\nMF_PWA_PORT=5180\n", encoding="utf-8"
    )
    services = _config(copie)
    assert _published(services["api_data"]) == ["8010"]
    assert _published(services["api_ia"]) == ["8011"]
    assert _published(services["pwa"]) == ["5180"]
    assert services["pwa"]["environment"] == {
        "MF_PUBLIC_API_DATA_URL": "http://localhost:8010",
        "MF_PUBLIC_API_IA_URL": "http://localhost:8011",
    }
    for api in ("api_data", "api_ia"):
        cors = services[api]["environment"]["MF_CORS_ORIGINS"].split(",")
        assert "http://localhost:5180" in cors and "http://localhost:5173" not in cors
