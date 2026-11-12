"""Outils des agents : des fonctions Python sûres, jamais de SQL écrit par le modèle.

Correspondance avec le cours : ``metadonnees_oeuvre`` (query_movie_metadata),
``oeuvres_similaires`` (find_similar_horror_movies), ``resume_web`` (scrape_detailed_synopsis),
``age_oeuvre`` (calculate_movie_age), ``trouver_oeuvre`` (routeur FAISS), ``chercher_passages`` (rag_tool).
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import quote

import httpx
from loguru import logger

from rag.moteur import MoteurRAG, Resultat
from rag.titres import IndexTitres


class ClientDonnees:
    """Client de l'API de données (réseau privé, clé de service)."""

    def __init__(self, url: str, cle: str, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(base_url=url, timeout=15)
        self.client.headers["X-API-Key"] = cle

    def oeuvre(self, oeuvre_id: int) -> dict[str, Any] | None:
        reponse = self.client.get(f"/oeuvres/{int(oeuvre_id)}")
        if reponse.status_code == 404:
            return None
        reponse.raise_for_status()
        return reponse.json()

    def toutes(self, taille: int = 200) -> Iterator[dict[str, Any]]:
        offset = 0
        while True:
            page = self.client.get("/oeuvres", params={"limit": taille, "offset": offset})
            page.raise_for_status()
            elements = page.json()["elements"]
            yield from elements
            offset += len(elements)
            if len(elements) < taille:
                return


class ClientWeb:
    """Résumé d'une page Wikipédia (API REST officielle, plutôt que l'analyse du HTML)."""

    def __init__(self, client: httpx.Client | None = None, langue: str = "fr", agent: str = "assistant-ia") -> None:
        self.client = client or httpx.Client(timeout=10, follow_redirects=True)
        self.client.headers["User-Agent"] = agent
        self.langue = langue

    def resume(self, titre: str) -> dict[str, str] | None:
        url = f"https://{self.langue}.wikipedia.org/api/rest_v1/page/summary/{quote(titre.replace(' ', '_'))}"
        try:
            reponse = self.client.get(url)
        except httpx.HTTPError as erreur:
            logger.warning("Wikipédia injoignable : {}", type(erreur).__name__)
            return None
        if reponse.status_code != 200:
            return None
        page = reponse.json()
        if page.get("type") == "disambiguation" or not page.get("extract"):
            return None
        lien = page.get("content_urls", {}).get("desktop", {}).get("page", url)
        return {"titre": page.get("title", titre), "extrait": page["extract"], "url": lien}


def age_oeuvre(annee: int, aujourd_hui: date | None = None) -> int:
    return (aujourd_hui or date.today()).year - int(annee)


@dataclass
class Outils:
    donnees: ClientDonnees
    titres: IndexTitres
    rag: MoteurRAG
    web: ClientWeb
    k: int = 4

    def trouver_oeuvre(self, question: str) -> tuple[int, str, float] | None:
        return self.titres.trouver(question)

    def metadonnees_oeuvre(self, oeuvre_id: int) -> dict[str, Any] | None:
        return self.donnees.oeuvre(oeuvre_id)

    def chercher_passages(self, question: str) -> list[Resultat]:
        return self.rag.chercher(question, self.k)

    def oeuvres_similaires(self, oeuvre_id: int, k: int = 3) -> list[dict[str, Any]]:
        return self.rag.similaires(oeuvre_id, k)

    def resume_web(self, titre: str) -> dict[str, str] | None:
        return self.web.resume(titre)

    @staticmethod
    def age_oeuvre(annee: int) -> int:
        return age_oeuvre(annee)

    def charger(self) -> int:
        """Remplit l'index des titres et le RAG depuis l'API de données ; renvoie le nombre d'œuvres."""
        oeuvres = list(self.donnees.toutes())
        self.titres.ajouter((o["id"], o["titre"]) for o in oeuvres)
        self.rag.indexer(oeuvres)
        return len(oeuvres)
