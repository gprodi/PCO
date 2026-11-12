"""API de données : clé de service, import idempotent, recherche sûre, fiches complètes."""

from fastapi.testclient import TestClient

from donnees.api import app
from tests.faux import FICHES


def test_cle_de_service_obligatoire(api_donnees, monkeypatch):
    sans_cle = TestClient(app)
    assert sans_cle.get("/oeuvres").status_code == 401
    assert sans_cle.get("/oeuvres", headers={"X-API-Key": "mauvaise"}).status_code == 401
    assert sans_cle.get("/health").json() == {"statut": "ok"}
    from commun.config import get_settings

    monkeypatch.setenv("APP_DATA_API_KEY", "")
    get_settings.cache_clear()
    assert api_donnees.get("/oeuvres").status_code == 503  # pas de clé configurée : refus par défaut


def test_import_idempotent_et_identifiants(api_donnees):
    assert api_donnees.post("/oeuvres/import", json=FICHES).json() == {"creees": 0, "mises_a_jour": 3}
    page = api_donnees.get("/oeuvres").json()
    assert page["total"] == 3
    dracula = next(o for o in page["elements"] if o["titre"] == "Dracula")
    assert dracula["ids"] == {"ref_catalogue": "OEU-001"} and dracula["provenance"] == {"titre": "csv"}
    renomme = {**FICHES[0], "titre": "Dracula (édition annotée)"}
    assert api_donnees.post("/oeuvres/import", json=[renomme]).json() == {"creees": 0, "mises_a_jour": 1}
    assert api_donnees.get(f"/oeuvres/{dracula['id']}").json()["titre"] == "Dracula (édition annotée)"


def test_recherche_et_pagination(api_donnees):
    assert [o["titre"] for o in api_donnees.get("/oeuvres", params={"q": "horla"}).json()["elements"]] == ["Le Horla"]
    assert api_donnees.get("/oeuvres", params={"q": "100%_"}).json()["total"] == 0  # jokers neutralisés
    assert api_donnees.get("/oeuvres", params={"annee": 1872}).json()["total"] == 1
    page = api_donnees.get("/oeuvres", params={"limit": 2, "offset": 2}).json()
    assert page["total"] == 3 and len(page["elements"]) == 1
    assert api_donnees.get("/oeuvres", params={"limit": 0}).status_code == 422
    assert api_donnees.get("/oeuvres/9999").status_code == 404


def test_metriques_exposees(api_donnees):
    assert "python_info" in api_donnees.get("/metrics/").text
