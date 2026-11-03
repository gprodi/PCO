from fastapi.testclient import TestClient

KEY = {"X-API-Key": "cle-de-test"}


def test_model_and_api_ia():
    from api_ia import model
    from api_ia.main import app

    assert model.predict("Livraison rapide, produit excellent")[0] == "positif"
    assert model.predict("Colis en retard et produit cassé")[0] == "negatif"
    assert model.predict("Reçu mardi") == ("neutre", 0.5)
    with TestClient(app) as c:
        assert c.post("/predict", json={"texte": "super"}).status_code == 401
        r = c.post("/predict", json={"texte": "super produit"}, headers=KEY)
        assert r.status_code == 200 and r.json()["sentiment"] == "positif"
        assert c.post("/predict", json={"texte": ""}, headers=KEY).status_code == 422


def test_api_data_crud_and_protection():
    from api_data.main import app

    body = {"texte": "Très bien", "sentiment": "positif", "score": 0.9}
    with TestClient(app) as c:
        assert c.post("/avis", json=body).status_code == 401
        created = c.post("/avis", json=body, headers=KEY)
        assert created.status_code == 201
        assert c.get(f"/avis/{created.json()['id']}").json()["texte"] == "Très bien"
        assert c.get("/avis/999").status_code == 404
        assert c.post("/avis", json={**body, "sentiment": "joyeux"}, headers=KEY).status_code == 422
        assert len(c.get("/avis", params={"limit": 5}).json()) == 1


def test_streamlit_app_survives_unreachable_services():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("../streamlit_app.py", default_timeout=30).run()
    assert not at.exception
    assert "Liste indisponible" in at.warning[0].value
