"""Pile Docker locale (profil core) : elle démarre sans fichier .env.

Les valeurs de développement versionnées (microforge/.env.example) servent par défaut ; un fichier
microforge/.env, s'il existe, les remplace. Vérifié sans démon par ``docker compose config``, sur
une copie temporaire du compose : le vrai .env de l'utilisateur n'est jamais lu ni modifié.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

MF = Path(__file__).resolve().parents[1]
DOCKER = shutil.which("docker")


def _config(root: Path) -> dict:
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


def test_le_fichier_env_remplace_les_valeurs_par_defaut(copie):
    (copie / ".env").write_text("MF_ENV=prod\nLLM_CHAIN=gemini\n", encoding="utf-8")
    env = _config(copie)["api_data"]["environment"]
    assert env["MF_ENV"] == "prod" and env["LLM_CHAIN"] == "gemini"
    assert env["MF_DATABASE_URL"].endswith("@postgres:5432/microforge")  # le reste garde le défaut
