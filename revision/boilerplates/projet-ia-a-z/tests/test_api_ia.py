"""API d'IA : comptes, rotation des jetons (rejeu détecté), /chat protégé, effacement, métriques."""

import pytest
from fastapi.testclient import TestClient

from agents.assistant import Assistant
from api_ia.main import creer_app, limiteur
from api_ia.metriques import mesurer_noeud
from api_ia.services import Services
from tests.faux import FauxLLM, passerelle

COMPTE = {"email": "Lecteur@Exemple.org", "mot_de_passe": "un mot de passe solide"}


@pytest.fixture
def api_ia(faire_outils):
    limiteur.reset()
    outils = faire_outils()
    assistant = Assistant(outils, passerelle(FauxLLM(["Réponse sourcée [1]."])), "le catalogue", mesure=mesurer_noeud)
    services = Services(outils, assistant)
    with TestClient(creer_app(lambda _reglages: services)) as client:
        yield client


def connecter(client: TestClient) -> dict[str, str]:
    assert client.post("/auth/inscription", json=COMPTE).status_code == 201
    jetons = client.post("/auth/jeton", data={"username": COMPTE["email"], "password": COMPTE["mot_de_passe"]})
    assert jetons.status_code == 200
    return jetons.json()


def test_inscription_connexion_et_erreurs(api_ia):
    connecter(api_ia)
    assert api_ia.post("/auth/inscription", json=COMPTE).status_code == 409
    assert api_ia.post("/auth/inscription", json={"email": "x@y.z", "mot_de_passe": "court"}).status_code == 422
    mauvais = api_ia.post("/auth/jeton", data={"username": COMPTE["email"], "password": "faux mot de passe"})
    inconnu = api_ia.post("/auth/jeton", data={"username": "personne@exemple.org", "password": "x" * 12})
    assert mauvais.status_code == inconnu.status_code == 401


def test_rotation_et_rejeu_du_jeton_de_rafraichissement(api_ia):
    premiers = connecter(api_ia)
    seconds = api_ia.post("/auth/rafraichir", json={"refresh_token": premiers["refresh_token"]})
    assert seconds.status_code == 200 and seconds.json()["refresh_token"] != premiers["refresh_token"]
    # Rejeu de l'ancien jeton : refusé, et toute la famille est révoquée (y compris le nouveau).
    assert api_ia.post("/auth/rafraichir", json={"refresh_token": premiers["refresh_token"]}).status_code == 401
    assert api_ia.post("/auth/rafraichir", json={"refresh_token": seconds.json()["refresh_token"]}).status_code == 401
    assert (
        api_ia.post("/auth/rafraichir", json={"refresh_token": premiers["access_token"]}).status_code == 401
    )  # mauvais type
    assert api_ia.post("/auth/rafraichir", json={"refresh_token": "n'importe quoi"}).status_code == 401


def test_deconnexion_revoque(api_ia):
    jetons = connecter(api_ia)
    assert api_ia.post("/auth/deconnexion", json={"refresh_token": jetons["refresh_token"]}).status_code == 204
    assert api_ia.post("/auth/rafraichir", json={"refresh_token": jetons["refresh_token"]}).status_code == 401
    assert api_ia.post("/auth/deconnexion", json={"refresh_token": "abime"}).status_code == 204


def test_chat_protege_puis_repond(api_ia):
    assert api_ia.post("/chat", json={"question": "Qui est Dracula ?"}).status_code == 401
    assert api_ia.post("/chat", json={"question": "x"}, headers={"Authorization": "Bearer faux"}).status_code == 401
    jetons = connecter(api_ia)
    entete = {"Authorization": f"Bearer {jetons['access_token']}"}
    reponse = api_ia.post("/chat", json={"question": "Qui est Dracula ?", "session": "s1"}, headers=entete)
    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps["reponse"] == "Réponse sourcée [1]." and corps["etapes"] == ["rag", "narration", "juge"]
    assert reponse.headers["X-Frame-Options"] == "DENY"
    assert api_ia.post("/chat", json={"question": "x"}, headers=entete).status_code == 422
    metriques = api_ia.get("/metrics/").text
    assert 'assistant_questions_total{fournisseur="ollama",verdict="ok"}' in metriques
    assert "assistant_noeud_secondes_bucket" in metriques
    assert api_ia.get("/health").json() == {"statut": "ok", "index_pret": True}


def test_effacement_du_compte(api_ia):
    jetons = connecter(api_ia)
    entete = {"Authorization": f"Bearer {jetons['access_token']}"}
    assert api_ia.delete("/auth/moi", headers=entete).status_code == 204
    assert api_ia.post("/chat", json={"question": "Qui est Dracula ?"}, headers=entete).status_code == 401
    assert api_ia.post("/auth/rafraichir", json={"refresh_token": jetons["refresh_token"]}).status_code == 401


def test_index_vide_et_api_de_donnees_absente(faire_outils):
    limiteur.reset()
    outils = faire_outils()
    outils.titres.titres.clear()

    def panne():
        raise ConnectionError("API de données arrêtée")

    outils.charger = panne
    services = Services(outils, Assistant(outils, passerelle(FauxLLM()), "le catalogue"))
    with TestClient(creer_app(lambda _r: services)) as client:
        jetons = connecter(client)
        entete = {"Authorization": f"Bearer {jetons['access_token']}"}
        assert client.post("/chat", json={"question": "Qui est Dracula ?"}, headers=entete).status_code == 503


def test_limite_de_tentatives_de_connexion(api_ia, monkeypatch):
    from commun.config import get_settings

    monkeypatch.setenv("APP_LOGIN_RATE", "2/minute")
    get_settings.cache_clear()
    codes = [api_ia.post("/auth/jeton", data={"username": "a@b.c", "password": "x" * 12}).status_code for _ in range(4)]
    assert codes[-1] == 429


def test_cle_de_signature_obligatoire(faire_outils, monkeypatch):
    from commun.config import get_settings

    monkeypatch.setenv("APP_SECRET_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="APP_SECRET_KEY"), TestClient(creer_app(lambda _r: None)):
        pass


def test_services_reels_construits_sans_reseau():
    from api_ia.services import construire
    from commun.config import get_settings

    services = construire(get_settings())
    assert not services.pret and services.charger() is False  # API de données injoignable : pas d'exception
