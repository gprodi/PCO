"""Assemblage des dépendances de l'API d'IA (remplaçables dans les tests)."""

import threading
from dataclasses import dataclass, field

from loguru import logger

from agents.assistant import Assistant
from agents.tools import ClientDonnees, ClientWeb, Outils
from api_ia.metriques import OEUVRES, mesurer_noeud, suivre_llm
from commun.config import Settings
from llm.passerelle import Passerelle
from rag.embeddings import EmbeddeurModele
from rag.index import IndexMemoire
from rag.moteur import MoteurRAG
from rag.titres import IndexTitres


@dataclass
class Services:
    outils: Outils
    assistant: Assistant
    _verrou: threading.Lock = field(default_factory=threading.Lock)

    def charger(self) -> bool:
        """Charge l'index depuis l'API de données ; faux si elle ne répond pas (nouvel essai plus tard)."""
        with self._verrou:
            try:
                n = self.outils.charger()
            except Exception as erreur:  # API de données pas encore prête
                logger.warning("Index non chargé : {}", erreur)
                return False
            OEUVRES.set(n)
            logger.info("{} œuvres indexées", n)
            return True

    @property
    def pret(self) -> bool:
        return len(self.outils.titres) > 0


def construire(s: Settings) -> Services:
    passerelle = Passerelle.depuis_reglages(s, suivi=suivre_llm)
    index = IndexMemoire()
    if s.vector_url:  # pragma: no cover - dépend d'un PostgreSQL
        from rag.index import IndexPgVector

        dimension = len(EmbeddeurModele(passerelle).encoder(["dimension"])[0])
        index = IndexPgVector(s.vector_url, dimension)
    outils = Outils(
        donnees=ClientDonnees(s.data_api_url, s.data_api_key),
        titres=IndexTitres(),
        rag=MoteurRAG(EmbeddeurModele(passerelle), index, seuil=s.rag_seuil),
        web=ClientWeb(langue=s.wiki_lang, agent=s.user_agent),
        k=s.rag_k,
    )
    return Services(outils, Assistant(outils, passerelle, s.domaine, mesure=mesurer_noeud))
