"""Le câblage : le StateGraph relie les nœuds (nodes.py) et les aiguillages (router.py).

START → rag ─┬─(suffisant)──────────→ narration → juge ─┬─(ok, repli)→ END
             └─(incomplet)→ scraper ─↗          ↖───────┘ (à revoir)
"""

import time
from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from agents.nodes import Noeud
from agents.router import apres_juge, apres_rag
from agents.state import AgentState


def _chronometre(nom: str, noeud: Noeud, mesure: Callable[[str, float], None]) -> Noeud:
    def enveloppe(state: AgentState) -> dict[str, Any]:
        debut = time.perf_counter()
        try:
            return noeud(state)
        finally:
            mesure(nom, time.perf_counter() - debut)

    enveloppe.__name__ = getattr(noeud, "__name__", nom)
    return enveloppe


def construire(noeuds: dict[str, Noeud], mesure: Callable[[str, float], None] | None = None):
    """Compile le graphe ; ``mesure(nom, secondes)`` reçoit la durée de chaque nœud (Prometheus)."""
    workflow = StateGraph(AgentState)
    for nom in ("rag", "scraper", "narration", "juge"):
        workflow.add_node(nom, _chronometre(nom, noeuds[nom], mesure) if mesure else noeuds[nom])
    workflow.add_edge(START, "rag")
    workflow.add_conditional_edges("rag", apres_rag, {"narration": "narration", "scraper": "scraper"})
    workflow.add_edge("scraper", "narration")
    workflow.add_edge("narration", "juge")
    workflow.add_conditional_edges("juge", apres_juge, {"narration": "narration", "fin": END})
    return workflow.compile()


def mermaid(noeuds: dict[str, Noeud]) -> str:
    """Schéma Mermaid du graphe (documentation)."""
    return construire(noeuds).get_graph().draw_mermaid()
