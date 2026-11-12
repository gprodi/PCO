"""Graphe multi-agent : aiguillages, juge, chemins complets (base, web, sans modèle), traces."""

import sys
import types

import httpx

from agents import nodes, router
from agents.assistant import Assistant
from agents.nodes import RIEN_TROUVE, creer_noeuds, problemes
from agents.observabilite import config_execution
from agents.pipeline import construire, mermaid
from agents.tools import age_oeuvre
from tests.faux import FauxLLM, passerelle

DOMAINE = "la littérature d'épouvante"


def test_aiguillage_apres_le_chercheur():
    long = {"resume": "x" * 200}
    assert router.apres_rag({"question": "Qui est Dracula ?", "oeuvre": long}) == "narration"
    assert router.apres_rag({"question": "Qui est Dracula ?", "oeuvre": {"resume": "court"}}) == "scraper"
    assert router.apres_rag({"question": "Une anecdote sur Dracula ?", "oeuvre": long}) == "scraper"
    assert router.apres_rag({"question": "vampires ?", "sources": [{"type": "passage"}]}) == "narration"
    assert router.apres_rag({"question": "vampires ?", "sources": []}) == "scraper"
    assert router.apres_juge({"verdict": "a_revoir"}) == "narration"
    assert router.apres_juge({"verdict": "ok"}) == "fin"


def test_controles_du_juge():
    assert problemes("", 2) == ["la réponse est vide"]
    assert problemes(RIEN_TROUVE, 0) == []
    assert "aucune source" in problemes("Sans citation.", 2)[0]
    assert "[3]" in problemes("Faux [3].", 2)[0]
    assert problemes("Juste [1] et [2].", 2) == []


def test_dossier_tronque_et_reponse_extractive():
    etat = {"sources": [{"type": "passage", "titre": "T", "extrait": "mot " * 400}], "oeuvre": None}
    assert nodes.dossier(etat, maximum=100).endswith("[dossier tronqué]")
    assert nodes.reponse_extractive({"sources": []}) == RIEN_TROUVE
    assert nodes.reponse_extractive(etat).endswith("[1]")


def test_chemin_base_suffisante(faire_outils):
    faux = FauxLLM(["Dracula (1897) est un roman de Bram Stoker [1] où Van Helsing traque le comte [2]."])
    assistant = Assistant(faire_outils(), passerelle(faux), DOMAINE)
    r = assistant.repondre("Qui traque Dracula ?")
    assert r.etapes == ["rag", "narration", "juge"] and r.verdict == "ok" and r.fournisseur == "ollama"
    assert r.sources[0]["type"] == "base" and r.sources[0]["titre"] == "Dracula"
    consigne = faux.appels[0][1]["messages"][1]["content"]
    assert "Fiche de la base — titre : Dracula ; année : 1897" in consigne
    assert DOMAINE in faux.appels[0][1]["messages"][0]["content"]


def test_chemin_enqueteur_web_pour_une_anecdote(faire_outils):
    faux = FauxLLM(["Stoker s'inspira de légendes [3]."])
    r = Assistant(faire_outils(), passerelle(faux), DOMAINE).repondre("Une anecdote sur Dracula ?")
    assert r.etapes == ["rag", "scraper", "narration", "juge"]
    web = [s for s in r.sources if s["type"] == "web"]
    assert web and web[0]["url"] == "https://fr.wikipedia.org/wiki/Dracula"


def test_enqueteur_sans_resultat_web(faire_outils):
    r = Assistant(faire_outils(), passerelle(FauxLLM(["Le Horla est de Maupassant [1]."])), DOMAINE)
    reponse = r.repondre("Parle-moi du Horla")
    assert reponse.etapes == ["rag", "scraper", "narration", "juge"]  # résumé absent : enquête, sans succès
    assert all(s["type"] != "web" for s in reponse.sources)


def test_juge_fait_corriger_puis_valide(faire_outils):
    faux = FauxLLM(["Dracula est un vampire.", "Dracula est un vampire [1]."])
    r = Assistant(faire_outils(), passerelle(faux), DOMAINE).repondre("Qui est Dracula ?")
    assert r.etapes == ["rag", "narration", "juge", "narration", "juge"] and r.verdict == "ok"
    assert "Correction demandée" in faux.appels[1][1]["messages"][1]["content"]


def test_juge_se_replie_sur_les_extraits(faire_outils):
    r = Assistant(faire_outils(), passerelle(FauxLLM(["Jamais de citation."])), DOMAINE).repondre("Qui est Dracula ?")
    assert r.verdict == "repli" and r.fournisseur == "extractif" and "[1]" in r.reponse


def test_sans_modele_de_langage_reponse_extractive(faire_outils):
    faux = FauxLLM(panne={"ollama", "gemini"})
    r = Assistant(faire_outils(), passerelle(faux), DOMAINE).repondre("Quel âge a Dracula ? Une œuvre similaire ?")
    assert r.fournisseur == "extractif" and r.verdict == "ok"
    assert r.reponse.count("Jonathan Harker") == 1  # la fiche n'est pas répétée par ses propres passages
    assert f"Dracula (1897, Bram Stoker), il y a {age_oeuvre(1897)} ans : Le clerc" in r.reponse
    assert "Œuvres proches : Carmilla" in r.reponse


def test_rien_trouve(faire_outils):
    def sans_web(_requete: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    outils = faire_outils(web=sans_web)
    outils.rag.seuil = 0.99
    faux = FauxLLM()
    r = Assistant(outils, passerelle(faux), DOMAINE).repondre("Quelle est la recette du gâteau ?")
    assert r.reponse == RIEN_TROUVE and r.fournisseur == "aucun" and faux.appels == []


def test_similaires_et_age(faire_outils):
    outils = faire_outils()
    faux = FauxLLM(["Proche de Carmilla [1]."])
    r = Assistant(outils, passerelle(faux), DOMAINE).repondre("Quel âge a Dracula et une œuvre similaire ?")
    assert r.similaires and r.similaires[0]["titre"] == "Carmilla"
    consigne = faux.appels[0][1]["messages"][1]["content"]
    assert f"âge : {age_oeuvre(1897)} ans" in consigne and "Œuvres aux résumés proches" in consigne


def test_outils_web_ambigu_et_injoignable(faire_outils):
    outils = faire_outils()
    assert outils.resume_web("Ambigu") is None

    def panne(_requete: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("hors ligne")

    assert faire_outils(web=panne).resume_web("Dracula") is None
    assert outils.metadonnees_oeuvre(9999) is None


def test_mesures_par_noeud_et_schema(faire_outils):
    durees: dict[str, float] = {}
    noeuds = creer_noeuds(faire_outils(), passerelle(FauxLLM(["Réponse [1]."])), DOMAINE)
    graphe = construire(noeuds, mesure=lambda nom, s: durees.__setitem__(nom, s))
    graphe.invoke({"question": "Qui est Dracula ?", "etapes": [], "essais": 0})
    assert set(durees) == {"rag", "narration", "juge"}
    schema = mermaid(noeuds)
    assert all(nom in schema for nom in ("rag", "scraper", "narration", "juge"))


def test_traces_langfuse(monkeypatch):
    assert config_execution("s1") == {}
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setitem(sys.modules, "langfuse", None)  # paquet absent
    monkeypatch.delitem(sys.modules, "langfuse.langchain", raising=False)
    assert config_execution("s1") == {}
    faux = types.ModuleType("langfuse.langchain")
    faux.CallbackHandler = lambda: "gestionnaire"
    monkeypatch.setitem(sys.modules, "langfuse", types.ModuleType("langfuse"))
    monkeypatch.setitem(sys.modules, "langfuse.langchain", faux)
    config = config_execution("s1", "7")
    assert config["callbacks"] == ["gestionnaire"]
    assert config["metadata"] == {"langfuse_session_id": "s1", "langfuse_user_id": "7"}
