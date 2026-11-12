"""Les aiguilleurs : lisent le State et renvoient le nom de la prochaine étape (rien d'autre)."""

import re

from agents.state import AgentState

#: résumé local jugé suffisant à partir de cette longueur (caractères)
RESUME_SUFFISANT = 150
DETAILS = re.compile(r"anecdote|détail|en savoir plus|tournage|coulisse|secret|origine", re.IGNORECASE)


def apres_rag(state: AgentState) -> str:
    """« narration » si la récolte locale suffit, sinon « scraper »."""
    if DETAILS.search(state["question"]):
        return "scraper"  # les anecdotes ne sont pas dans la base
    oeuvre = state.get("oeuvre")
    if oeuvre:
        return "narration" if len(oeuvre.get("resume") or "") >= RESUME_SUFFISANT else "scraper"
    passages = [s for s in state.get("sources", []) if s["type"] == "passage"]
    return "narration" if passages else "scraper"


def apres_juge(state: AgentState) -> str:
    """Retour au narrateur si le juge demande une correction, sinon fin."""
    return "narration" if state.get("verdict") == "a_revoir" else "fin"
