"""Interface : client (jetons, renouvellement, erreurs) et page Streamlit (AppTest)."""

import json

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from tests.faux import RACINE
from ui import client as module_client
from ui.client import ClientAPI, ErreurAPI

REPONSE = {"reponse": "Dracula est de Bram Stoker [1].", "sources": [{"type": "web", "titre": "Dracula", "url": "https://fr.wikipedia.org/wiki/Dracula"}],
           "etapes": ["rag", "narration", "juge"], "verdict": "ok", "fournisseur": "ollama", "similaires": []}  # fmt: skip


class FausseAPI:
    def __init__(self, acces_valides: set[str] | None = None, rafraichir_ok: bool = True) -> None:
        self.acces_valides = acces_valides or {"A2"}
        self.rafraichir_ok = rafraichir_ok
        self.chemins: list[str] = []

    def __call__(self, requete: httpx.Request) -> httpx.Response:
        self.chemins.append(requete.url.path)
        match requete.url.path:
            case "/auth/inscription":
                corps = json.loads(requete.content)
                if len(corps["mot_de_passe"]) < 12:
                    return httpx.Response(422, json={"detail": [{"msg": "trop court"}]})
                return httpx.Response(201, json={"id": 1})
            case "/auth/jeton":
                if b"password=bon" not in requete.content:
                    return httpx.Response(401, json={"detail": "Identifiants invalides"})
                return httpx.Response(200, json={"access_token": "A1", "refresh_token": "R1"})
            case "/auth/rafraichir":
                if not self.rafraichir_ok:
                    return httpx.Response(401, json={"detail": "Identifiants invalides"})
                return httpx.Response(200, json={"access_token": "A2", "refresh_token": "R2"})
            case "/auth/deconnexion":
                return httpx.Response(204)
            case "/chat":
                if requete.headers["Authorization"].removeprefix("Bearer ") not in self.acces_valides:
                    return httpx.Response(401, json={"detail": "Identifiants invalides"})
                return httpx.Response(200, json=REPONSE)
        return httpx.Response(500, text="")


def client_sur(api: FausseAPI) -> ClientAPI:
    return ClientAPI("http://ia.test", httpx.Client(base_url="http://ia.test", transport=httpx.MockTransport(api)))


def test_connexion_question_et_renouvellement_du_jeton():
    api = FausseAPI()
    client = client_sur(api)
    with pytest.raises(ErreurAPI, match="Connectez-vous"):
        client.poser("Qui ?")
    client.inscrire("a@b.c", "x" * 12)
    with pytest.raises(ErreurAPI, match="trop court"):
        client.inscrire("a@b.c", "court")
    with pytest.raises(ErreurAPI, match="Identifiants invalides"):
        client.connecter("a@b.c", "mauvais")
    client.connecter("a@b.c", "bon")
    assert client.poser("Qui est Dracula ?")["reponse"] == REPONSE["reponse"]
    assert api.chemins[-3:] == ["/chat", "/auth/rafraichir", "/chat"]  # A1 expiré → A2
    client.deconnecter()
    assert not client.connecte


def test_renouvellement_refuse_et_erreurs_reseau():
    client = client_sur(FausseAPI(rafraichir_ok=False))
    client.connecter("a@b.c", "bon")
    with pytest.raises(ErreurAPI) as erreur:
        client.poser("Qui ?")
    assert erreur.value.code == 401 and not client.connecte

    def panne(_requete):
        raise httpx.ConnectError("refus")

    hors_ligne = ClientAPI("http://ia.test", httpx.Client(transport=httpx.MockTransport(panne)))
    with pytest.raises(ErreurAPI, match="injoignable"):
        hors_ligne.connecter("a@b.c", "bon")
    assert module_client._detail(httpx.Response(500, text="")) == "erreur 500"


def page() -> AppTest:
    return AppTest.from_file(str(RACINE / "streamlit_app.py"), default_timeout=30)


def test_page_invite_a_se_connecter():
    app = page().run()
    assert not app.exception
    assert "Connectez-vous" in app.info[0].value


def test_page_connexion_puis_question(monkeypatch):
    api = FausseAPI(acces_valides={"A1"})
    monkeypatch.setattr(module_client, "ClientAPI", lambda url: client_sur(api))
    app = page().run()
    app.sidebar.text_input[0].input("a@b.c")
    app.sidebar.text_input[1].input("bon")
    app.sidebar.button[0].click().run()
    assert not app.exception and app.sidebar.success[0].value == "Connecté"
    app.chat_input[0].set_value("Qui a écrit Dracula ?").run()
    assert not app.exception
    textes = [m.value for m in app.markdown]
    assert REPONSE["reponse"] in textes and any("[1]" in t and "lien" in t for t in textes)
    app.sidebar.button[0].click().run()
    assert "Connectez-vous" in app.info[0].value


def test_page_affiche_les_erreurs(monkeypatch):
    api = FausseAPI(acces_valides=set(), rafraichir_ok=False)
    monkeypatch.setattr(module_client, "ClientAPI", lambda url: client_sur(api))
    app = page().run()
    app.sidebar.radio[0].set_value("Inscription").run()
    app.sidebar.text_input[0].input("a@b.c")
    app.sidebar.text_input[1].input("court")
    app.sidebar.button[0].click().run()
    assert "trop court" in app.sidebar.error[0].value
    app.sidebar.radio[0].set_value("Connexion").run()
    app.sidebar.text_input[1].input("bon")
    app.sidebar.button[0].click().run()
    app.chat_input[0].set_value("Qui ?").run()
    assert any("Identifiants invalides" in e.value for e in app.error)
