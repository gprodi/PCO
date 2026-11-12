"""Doubles de test sans réseau : modèles (Ollama, Gemini) et Wikipédia simulés, données d'exemple."""

import json
from pathlib import Path

import httpx

from llm.passerelle import Fournisseur, Passerelle

RACINE = Path(__file__).resolve().parents[1]
CLE = "cle-de-service-pour-les-tests"
SECRET = "secret-de-test-assez-long-pour-hs256-0123456789"

DRACULA = (
    "Le clerc de notaire Jonathan Harker se rend en Transylvanie chez le comte Dracula, qui projette "
    "de s'installer à Londres. Lettres et journaux intimes racontent ensuite la traque du vampire par "
    "le professeur Van Helsing et ses compagnons."
)
FICHES = [
    {"titre": "Dracula", "annee": 1897, "auteur": "Bram Stoker", "genre": "Horreur", "resume": DRACULA,
     "note": 8.1, "ids": {"ref_catalogue": "OEU-001"}, "provenance": {"titre": "csv"}, "sources": ["csv"]},
    {"titre": "Carmilla", "annee": 1872, "auteur": "Joseph Sheridan Le Fanu", "genre": "Horreur",
     "resume": "Dans un château de Styrie, Laura se lie avec Carmilla, une vampire, tandis que les jeunes filles dépérissent.",
     "ids": {}, "provenance": {}, "sources": ["csv"]},
    {"titre": "Le Horla", "annee": 1887, "auteur": "Guy de Maupassant", "genre": "Fantastique", "resume": None,
     "ids": {}, "provenance": {}, "sources": ["sql"]},
]  # fmt: skip


def reponse_llm(texte: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": texte}}]}


class FauxLLM:
    """Transport httpx qui joue Ollama et Gemini : réponses programmées, appels enregistrés."""

    def __init__(self, reponses: list[str] | None = None, panne: set[str] | None = None) -> None:
        self.reponses = list(reponses or ["Dracula est un roman de Bram Stoker [1]."])
        self.panne = panne or set()
        self.appels: list[tuple[str, dict]] = []

    def __call__(self, requete: httpx.Request) -> httpx.Response:
        hote = "gemini" if "googleapis" in str(requete.url) else "ollama"
        corps = json.loads(requete.content or b"{}")
        self.appels.append((f"{hote}{requete.url.path}", corps))
        if hote in self.panne:
            return httpx.Response(503, json={"error": "indisponible"})
        if requete.url.path.endswith("/embeddings"):
            return httpx.Response(
                200, json={"data": [{"index": i, "embedding": [1.0, float(i)]} for i in range(len(corps["input"]))]}
            )
        texte = self.reponses.pop(0) if len(self.reponses) > 1 else self.reponses[0]
        return httpx.Response(200, json=reponse_llm(texte))


def passerelle(faux: FauxLLM, gemini: bool = True, **options) -> Passerelle:
    fournisseurs = [Fournisseur("ollama", "http://ollama.test/v1", "ollama", "qwen3:4b", "bge-m3")]
    if gemini:
        fournisseurs.append(
            Fournisseur(
                "gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "cle", "gemini-flash-latest", "e"
            )
        )
    return Passerelle(fournisseurs, httpx.Client(transport=httpx.MockTransport(faux)), **options)


def wikipedia(requete: httpx.Request) -> httpx.Response:
    if "Dracula" in requete.url.path:
        return httpx.Response(200, json={
            "type": "standard", "title": "Dracula",
            "extract": "Dracula est un roman épistolaire publié en 1897 ; Stoker s'inspira de légendes d'Europe centrale.",
            "content_urls": {"desktop": {"page": "https://fr.wikipedia.org/wiki/Dracula"}},
        })  # fmt: skip
    if "Ambigu" in requete.url.path:
        return httpx.Response(200, json={"type": "disambiguation", "title": "Ambigu", "extract": "Plusieurs sens"})
    return httpx.Response(404, json={})
