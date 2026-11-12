"""Modèle de démonstration (lexique). Remplacez ``predict`` par votre vrai modèle."""

import re

POSITIF = {
    "bien",
    "bon",
    "bonne",
    "excellent",
    "parfait",
    "rapide",
    "super",
    "génial",
    "recommande",
    "aime",
}
NEGATIF = {
    "mauvais",
    "mauvaise",
    "lent",
    "cassé",
    "nul",
    "déçu",
    "déçue",
    "retard",
    "panne",
    "horrible",
}
VERSION = "lexique-1"


def predict(texte: str) -> tuple[str, float]:
    mots = re.findall(r"\w+", texte.lower())
    pos = sum(m in POSITIF for m in mots)
    neg = sum(m in NEGATIF for m in mots)
    if pos == neg:
        return "neutre", 0.5
    label = "positif" if pos > neg else "negatif"
    return label, round(max(pos, neg) / (pos + neg), 3)
