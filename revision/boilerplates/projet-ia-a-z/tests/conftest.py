"""Fixtures : réglages isolés, API de données remplie, outils des agents branchés sur des doubles."""

from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from agents.tools import ClientDonnees, ClientWeb, Outils
from api_ia import comptes
from commun.config import get_settings
from donnees import db
from rag.embeddings import EmbeddeurHache
from rag.moteur import MoteurRAG
from rag.titres import IndexTitres
from tests.faux import CLE, FICHES, SECRET, wikipedia


@pytest.fixture(autouse=True)
def reglages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for nom in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        monkeypatch.delenv(nom, raising=False)
    monkeypatch.setenv("APP_DATA_API_KEY", CLE)
    monkeypatch.setenv("APP_SECRET_KEY", SECRET)
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{tmp_path / 'donnees.db'}")
    monkeypatch.setenv("APP_AUTH_DATABASE_URL", f"sqlite:///{tmp_path / 'comptes.db'}")
    monkeypatch.setenv("APP_LOGIN_RATE", "1000/minute")
    monkeypatch.setenv("APP_CHAT_RATE", "1000/minute")
    monkeypatch.setenv("APP_DOMAINE", "la littérature d'épouvante")

    def vider() -> None:
        for moteur in (db.moteur, comptes.moteur):
            if moteur.cache_info().currsize:
                moteur().dispose()
            moteur.cache_clear()
        get_settings.cache_clear()

    vider()
    yield
    vider()


@pytest.fixture
def api_donnees() -> Iterator[TestClient]:
    from donnees.api import app

    with TestClient(app, headers={"X-API-Key": CLE}) as client:
        assert client.post("/oeuvres/import", json=FICHES).status_code == 200
        yield client


@pytest.fixture
def faire_outils(api_donnees: TestClient) -> Callable[..., Outils]:
    def fabrique(web: Callable[[httpx.Request], httpx.Response] = wikipedia) -> Outils:
        outils = Outils(
            donnees=ClientDonnees("http://donnees.test", CLE, client=api_donnees),
            titres=IndexTitres(),
            rag=MoteurRAG(EmbeddeurHache(), seuil=0.05),
            web=ClientWeb(httpx.Client(transport=httpx.MockTransport(web))),
        )
        outils.charger()
        return outils

    return fabrique
