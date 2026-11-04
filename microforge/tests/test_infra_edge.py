"""Préproduction derrière Traefik : configuration compose fusionnée, validée par ``docker compose config``.

Pas de démon Docker nécessaire : la commande fusionne et valide les fichiers. Ignoré si le client
Docker Compose est absent.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

INFRA = Path(__file__).resolve().parents[1] / "infra"
DOCKER = shutil.which("docker")
FILES = [
    "-f",
    "docker-compose.yml",
    "-f",
    "docker-compose.edge.yml",
    "--profile",
    "core",
    "--profile",
    "edge",
]


def _config(**env: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [DOCKER, "compose", *FILES, "config"],
        cwd=INFRA,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


@pytest.fixture(scope="module")
def merged() -> dict:
    if (
        DOCKER is None
        or subprocess.run([DOCKER, "compose", "version"], capture_output=True).returncode
    ):
        pytest.skip("Docker Compose absent")
    proc = _config(MF_DOMAIN="microforge.example.org", ACME_EMAIL="contact@example.org")
    assert proc.returncode == 0, proc.stderr
    return yaml.safe_load(proc.stdout)


def test_only_traefik_is_published(merged):
    published = {
        name: sorted(str(p.get("published")) for p in svc.get("ports", []))
        for name, svc in merged["services"].items()
        if svc.get("ports")
    }
    assert published == {"traefik": ["443", "80"]}


def test_routes_are_https_with_security_headers(merged):
    services = merged["services"]
    expected = {"pwa": "app", "streamlit": "poc", "api_data": "api", "api_ia": "ia"}
    for name, sub in expected.items():
        labels = services[name]["labels"]
        assert labels["traefik.enable"] == "true"
        router = next(k.split(".")[3] for k in labels if k.endswith(".rule"))
        assert (
            labels[f"traefik.http.routers.{router}.rule"] == f"Host(`{sub}.microforge.example.org`)"
        )
        assert labels[f"traefik.http.routers.{router}.entrypoints"] == "websecure"
        assert labels[f"traefik.http.routers.{router}.middlewares"] == "securite@docker"
        assert "frontend" in services[name]["networks"]
    # La PWA appelle les deux API depuis le navigateur : CORS limité à son origine, sur les deux.
    for api in ("api_data", "api_ia"):
        cors = services[api]["environment"]["MF_CORS_ORIGINS"]
        assert cors == "https://app.microforge.example.org"


def test_pwa_targets_public_https_apis(merged):
    pwa = merged["services"]["pwa"]
    assert pwa["environment"] == {
        "MF_PUBLIC_API_DATA_URL": "https://api.microforge.example.org",
        "MF_PUBLIC_API_IA_URL": "https://ia.microforge.example.org",
    }
    assert pwa["labels"]["traefik.http.services.app.loadbalancer.server.port"] == "8080"
    assert pwa["build"]["context"].endswith("microforge/pwa")


def test_traefik_is_pinned_and_locked_down(merged):
    traefik = merged["services"]["traefik"]
    assert re.fullmatch(r"traefik:v\d+\.\d+\.\d+", traefik["image"])
    command = traefik["command"]
    for flag in (
        "--providers.docker.exposedbydefault=false",
        "--entrypoints.web.http.redirections.entrypoint.to=websecure",
        "--certificatesresolvers.le.acme.email=contact@example.org",
        "--api.dashboard=false",
    ):
        assert flag in command, flag
    sock = next(v for v in traefik["volumes"] if v["source"] == "/var/run/docker.sock")
    assert sock["read_only"] is True
    labels = traefik["labels"]
    assert labels["traefik.http.middlewares.securite.headers.stsSeconds"] == "31536000"
    assert labels["traefik.http.middlewares.securite.headers.frameDeny"] == "true"


def test_missing_domain_is_refused(merged):
    env = {k: v for k, v in os.environ.items() if k not in {"MF_DOMAIN", "ACME_EMAIL"}}
    proc = subprocess.run(
        [DOCKER, "compose", *FILES, "config"],
        cwd=INFRA,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode != 0 and "requis" in proc.stderr
