"""Fixtures communes : configuration isolée (SQLite temporaire, clés éphémères, LLM simulé)."""

from __future__ import annotations

import io

import pytest
from microforge.common.security import generate_keypair
from PIL import Image


def _clear_caches() -> None:
    from microforge.api_data import db
    from microforge.api_ia import deps
    from microforge.common import security, settings

    settings.get_settings.cache_clear()
    security.signing_keys.cache_clear()
    security.fernet.cache_clear()
    db.get_engine.cache_clear()
    deps.public_key.cache_clear()
    deps.services.cache_clear()


@pytest.fixture
def mf_env(tmp_path, monkeypatch):
    keys = generate_keypair()
    monkeypatch.setenv("MF_ENV", "dev")
    monkeypatch.setenv("MF_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("MF_JWT_PRIVATE_KEY", keys.private_pem.replace("\n", "\\n"))
    monkeypatch.setenv("MF_JWT_PUBLIC_KEY", keys.public_pem.replace("\n", "\\n"))
    monkeypatch.setenv("MF_RATE_LIMIT_TOKEN", "1000/minute")
    monkeypatch.setenv("MF_RATE_LIMIT_VISION", "1000/hour")
    monkeypatch.setenv("LLM_CHAIN", "fake")
    monkeypatch.setenv("LLM_PROFILE", "cpu")
    _clear_caches()
    yield keys
    _clear_caches()


@pytest.fixture
def data_client(mf_env):
    from fastapi.testclient import TestClient
    from microforge.api_data.limiter import limiter
    from microforge.api_data.main import create_app

    limiter.reset()
    with TestClient(create_app()) as client:
        yield client


@pytest.fixture
def ia_client(mf_env):
    from fastapi.testclient import TestClient
    from microforge.api_ia.main import create_app, limiter

    limiter.reset()
    with TestClient(create_app()) as client:
        yield client


def register_and_login(client, username="gael", password="motdepasse123", email=None) -> dict:
    email = email or f"{username}@example.org"
    r = client.post(
        "/v1/auth/register",
        json={"username": username, "email": email, "password": password, "city": "Saint-Denis"},
    )
    assert r.status_code == 201, r.text
    r = client.post("/v1/auth/token", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def jpeg_with_gps() -> bytes:
    img = Image.new("RGB", (1600, 1200), (40, 120, 60))
    exif = Image.Exif()
    exif[0x010F] = "AppareilTest"  # Make
    exif[0x8825] = {1: "N", 2: (48.0, 51.0, 24.0)}  # GPSInfo
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()
