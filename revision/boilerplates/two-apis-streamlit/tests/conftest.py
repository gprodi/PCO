import pytest


@pytest.fixture(autouse=True)
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("API_KEY", "cle-de-test-assez-longue")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'avis.db'}")
    monkeypatch.setenv("DATA_URL", "http://127.0.0.1:9")  # port fermé : services injoignables
    monkeypatch.setenv("IA_URL", "http://127.0.0.1:9")
    from common.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
