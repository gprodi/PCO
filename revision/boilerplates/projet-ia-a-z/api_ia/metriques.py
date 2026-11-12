"""Métriques Prometheus de l'API d'IA (exposées sur /metrics)."""

from prometheus_client import Counter, Gauge, Histogram

REQUETES = Counter("assistant_http_requetes_total", "Requêtes HTTP", ["route", "methode", "code"])
LATENCE = Histogram("assistant_http_secondes", "Durée des requêtes HTTP", ["route"])
QUESTIONS = Counter("assistant_questions_total", "Questions traitées", ["verdict", "fournisseur"])
NOEUDS = Histogram(
    "assistant_noeud_secondes",
    "Durée de chaque nœud du graphe",
    ["noeud"],
    buckets=(0.05, 0.2, 0.5, 1, 2, 5, 10, 30, 60),
)
LLM = Counter("assistant_llm_appels_total", "Appels aux modèles de langage", ["fournisseur", "resultat"])
OEUVRES = Gauge("assistant_oeuvres_indexees", "Œuvres connues de l'index")


def mesurer_noeud(nom: str, secondes: float) -> None:
    NOEUDS.labels(nom).observe(secondes)


def suivre_llm(fournisseur: str, resultat: str) -> None:
    LLM.labels(fournisseur, resultat).inc()
