"""Le State : la mémoire commune que les nœuds du graphe lisent et complètent."""

import operator
from typing import Annotated, Any, TypedDict


class AgentState(TypedDict, total=False):
    question: str
    #: fiche de l'œuvre reconnue dans la question (API de données), ou None
    oeuvre: dict[str, Any] | None
    #: dossier numéroté : fiche de la base, passages du RAG, extrait web
    sources: list[dict[str, Any]]
    similaires: list[dict[str, Any]]
    age: int | None
    mode_recherche: str | None
    reponse: str
    #: ollama, gemini, extractif (sans modèle) ou aucun
    fournisseur: str
    #: ok, a_revoir (le juge renvoie au narrateur) ou repli (réponse extractive)
    verdict: str
    consigne_juge: str
    essais: int
    #: nœuds traversés, dans l'ordre (réducteur : chaque nœud ajoute le sien)
    etapes: Annotated[list[str], operator.add]
