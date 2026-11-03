import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "x" * 64)
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    from app import config, db

    config.get_settings.cache_clear()
    db._engine = None
    from app.main import app, limiter

    limiter.reset()
    with TestClient(app) as c:
        yield c
