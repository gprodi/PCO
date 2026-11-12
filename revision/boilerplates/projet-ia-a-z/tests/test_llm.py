"""Passerelle : Ollama puis Gemini, réponses nettoyées, JSON validé, embeddings."""

import pytest
from pydantic import BaseModel

from commun.config import Settings
from llm.passerelle import LLMIndisponible, Passerelle
from tests.faux import FauxLLM, passerelle


def test_ollama_repond_en_premier_et_la_pensee_est_retiree():
    faux = FauxLLM(["<think>je réfléchis</think> Bonjour [1]"])
    suivi: list[tuple[str, str]] = []
    generation = passerelle(faux, suivi=lambda f, r: suivi.append((f, r))).generer("système", "question")
    assert generation.texte == "Bonjour [1]" and generation.fournisseur == "ollama"
    chemin, corps = faux.appels[0]
    assert chemin == "ollama/v1/chat/completions" and corps["messages"][0] == {"role": "system", "content": "système"}
    assert suivi == [("ollama", "ok")]


def test_repli_sur_gemini_puis_indisponible():
    suivi: list[tuple[str, str]] = []
    generation = passerelle(FauxLLM(panne={"ollama"}), suivi=lambda f, r: suivi.append((f, r))).generer("s", "q")
    assert generation.fournisseur == "gemini" and suivi == [("ollama", "echec"), ("gemini", "ok")]
    with pytest.raises(LLMIndisponible):
        passerelle(FauxLLM(panne={"ollama", "gemini"})).generer("s", "q")


class Avis(BaseModel):
    note: int
    resume: str


def test_json_valide_apres_une_relance():
    faux = FauxLLM(['{"note": "beaucoup"}', '```json\n{"note": 4, "resume": "bien"}\n```'])
    avis, fournisseur = passerelle(faux).generer_json("s", "Donne un avis", Avis)
    assert avis == Avis(note=4, resume="bien") and fournisseur == "ollama"
    assert "invalide" in faux.appels[1][1]["messages"][1]["content"]
    with pytest.raises(LLMIndisponible):
        passerelle(FauxLLM(["pas du json"])).generer_json("s", "q", Avis)


def test_embeddings_du_premier_fournisseur_seulement():
    assert passerelle(FauxLLM()).encoder(["a", "b"]) == [[1.0, 0.0], [1.0, 1.0]]
    with pytest.raises(LLMIndisponible):
        passerelle(FauxLLM(panne={"ollama"})).encoder(["a"])


def test_construction_depuis_les_reglages():
    assert [f.nom for f in Passerelle.depuis_reglages(Settings(_env_file=None, gemini_api_key="")).fournisseurs] == [
        "ollama"
    ]
    avec_cle = Passerelle.depuis_reglages(Settings(_env_file=None, gemini_api_key="cle-gratuite"))
    assert [f.nom for f in avec_cle.fournisseurs] == ["ollama", "gemini"]
    with pytest.raises(ValueError, match="32 caractères"):
        Settings(secret_key="court")
