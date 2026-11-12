"""Appel de l'API de prédiction, avec repli local quand aucune API n'est configurée."""

import os
import re

import httpx


class ApiError(RuntimeError):
    pass


def _local_model(text: str) -> dict:
    """Repli hors ligne : mini-lexique, pour que l'application reste démontrable sans serveur."""
    words = re.findall(r"\w+", text.lower())
    pos = sum(w in {"bien", "bon", "super", "excellent", "rapide", "parfait"} for w in words)
    neg = sum(w in {"mauvais", "lent", "nul", "cassé", "retard", "déçu"} for w in words)
    if pos == neg:
        return {"sentiment": "neutre", "score": 0.5, "source": "modèle local"}
    label = "positif" if pos > neg else "negatif"
    return {
        "sentiment": label,
        "score": round(max(pos, neg) / (pos + neg), 2),
        "source": "modèle local",
    }


def predict(text: str) -> dict:
    url = os.environ.get("API_URL")
    if not url:
        return _local_model(text)
    try:
        r = httpx.post(f"{url}/predict", json={"texte": text}, timeout=10)
        r.raise_for_status()
        return {**r.json(), "source": url}
    except httpx.HTTPError as exc:
        raise ApiError(f"API injoignable ou en erreur ({type(exc).__name__})") from exc
