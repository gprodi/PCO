"""L'assistant : le graphe compilé, prêt à répondre (utilisé par l'API d'IA)."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from agents.nodes import creer_noeuds
from agents.observabilite import config_execution
from agents.pipeline import construire
from agents.tools import Outils
from llm.passerelle import Passerelle


@dataclass
class Reponse:
    reponse: str
    sources: list[dict[str, Any]]
    etapes: list[str]
    verdict: str
    fournisseur: str
    similaires: list[dict[str, Any]] = field(default_factory=list)


class Assistant:
    def __init__(
        self, outils: Outils, llm: Passerelle, domaine: str, mesure: Callable[[str, float], None] | None = None
    ) -> None:
        self.outils = outils
        self.graphe = construire(creer_noeuds(outils, llm, domaine), mesure)

    def repondre(self, question: str, session: str | None = None, utilisateur: str | None = None) -> Reponse:
        config = {**config_execution(session, utilisateur), "recursion_limit": 12}
        etat = self.graphe.invoke({"question": question, "etapes": [], "essais": 0}, config=config)
        return Reponse(
            reponse=etat["reponse"],
            sources=etat.get("sources", []),
            etapes=etat["etapes"],
            verdict=etat.get("verdict", "ok"),
            fournisseur=etat.get("fournisseur", "aucun"),
            similaires=etat.get("similaires", []),
        )
