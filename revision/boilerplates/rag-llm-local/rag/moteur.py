"""Moteur RAG : indexation des résumés, recherche par vecteurs, repli lexical, œuvres similaires."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from loguru import logger

from llm.passerelle import LLMIndisponible
from rag.decoupage import decouper
from rag.embeddings import Embeddeur, normer
from rag.index import BM25, IndexMemoire, Passage


@dataclass(frozen=True)
class Resultat:
    passage: Passage
    score: float
    #: « vecteurs » (modèle d'embeddings) ou « lexical » (repli BM25)
    mode: str


class MoteurRAG:
    def __init__(self, embeddeur: Embeddeur, index: Any = None, seuil: float = 0.25, lot: int = 64) -> None:
        self.embeddeur = embeddeur
        self.index = index if index is not None else IndexMemoire()
        self.seuil = seuil
        self.lot = lot
        self.bm25 = BM25([])
        self.vecteurs_ok = True

    @staticmethod
    def passages(oeuvres: Iterable[dict[str, Any]]) -> list[Passage]:
        sortie = []
        for o in oeuvres:
            entete = f"{o['titre']} ({o.get('annee') or 'année inconnue'}, {o.get('auteur') or 'auteur inconnu'})."
            morceaux = decouper(o.get("resume") or "") or [""]
            for i, morceau in enumerate(morceaux):
                sortie.append(Passage(f"{o['id']}-{i}", o["id"], o["titre"], f"{entete} {morceau}".strip()))
        return sortie

    def indexer(self, oeuvres: Iterable[dict[str, Any]]) -> int:
        """(Ré)indexe tout ; sans modèle d'embeddings, seul l'index lexical est construit."""
        passages = self.passages(oeuvres)
        self.bm25 = BM25(passages)
        try:
            vecteurs: list[list[float]] = []
            for debut in range(0, len(passages), self.lot):
                vecteurs += self.embeddeur.encoder([p.texte for p in passages[debut : debut + self.lot]])
        except LLMIndisponible as erreur:
            logger.warning("Index vectoriel non construit ({}) : recherche lexicale seule", erreur)
            self.vecteurs_ok = False
            return len(passages)
        self.index.vider()
        self.index.ajouter(passages, vecteurs)
        self.vecteurs_ok = True
        logger.info("{} passages indexés ({})", len(passages), self.embeddeur.nom)
        return len(passages)

    def chercher(self, question: str, k: int = 4) -> list[Resultat]:
        if self.vecteurs_ok:
            try:
                vecteur = self.embeddeur.encoder([question])[0]
            except LLMIndisponible:
                logger.warning("Embeddings indisponibles : repli lexical")
            else:
                trouves = self.index.chercher(vecteur, k)
                return [Resultat(p, round(s, 3), "vecteurs") for p, s in trouves if s >= self.seuil]
        return [Resultat(p, round(s, 3), "lexical") for p, s in self.bm25.chercher(question, k)]

    def similaires(self, oeuvre_id: int, k: int = 3) -> list[dict[str, Any]]:
        """Œuvres dont les résumés sont les plus proches (moyenne des vecteurs de l'œuvre)."""
        vecteurs = self.index.vecteurs_de(oeuvre_id) if self.vecteurs_ok else []
        if not vecteurs:
            return []
        centre = normer([sum(composantes) / len(vecteurs) for composantes in zip(*vecteurs, strict=True)])
        vues: dict[int, dict[str, Any]] = {}
        for passage, score in self.index.chercher(centre, 5 * k + len(vecteurs)):
            if passage.oeuvre_id != oeuvre_id and passage.oeuvre_id not in vues:
                vues[passage.oeuvre_id] = {"id": passage.oeuvre_id, "titre": passage.titre, "score": round(score, 3)}
        return list(vues.values())[:k]
