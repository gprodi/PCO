"""Classement des articles : thématiques du plan de veille, fiabilité de la source, fraîcheur."""

from __future__ import annotations

import unicodedata
from datetime import UTC, datetime, timedelta

from microforge.veille.sources import Item

#: Mots-clés par thématique (plan-de-veille.md) ; recherchés sans accents ni casse.
THEMES: dict[str, list[str]] = {
    "T1": ["yolo", "detr", "vision", "vlm", "qwen", "gemma", "moondream", "detection",
           "quantiz", "gguf", "multimodal", "segmentation", "ocr"],
    "T2": ["ollama", "litellm", "llama.cpp", "vllm", "supply chain", "pypi", "cve", "vulnerab",
           "faille", "securite", "security", "docker", "pgvector", "embedding", "rag", "agent"],
    "T3": ["ai act", "reglement", "rgpd", "gdpr", "cnil", "donnees personnelles", "article 50",
           "omnibus", "transparence", "conformite"],
    "T4": ["accessibilite", "accessibility", "rgaa", "wcag", "eaa", "rgesn", "eco-conception",
           "lecteur d'ecran", "aria"],
    "T5": ["esp32", "arduino", "raspberry", "pico", "rp2040", "rp2350", "kicad", "wokwi",
           "espressif", "microcontroleur", "microcontroller", "maker", "capteur", "sensor"],
}  # fmt: skip
#: Briques de MicroForge : un avis de sécurité générique (CERT-FR) n'est retenu que s'il en cite une.
STACK = ["python", "pypi", "fastapi", "starlette", "pydantic", "uvicorn", "streamlit", "docker",
         "postgresql", "postgres", "pgvector", "redis", "traefik", "nginx", "ollama", "litellm",
         "github actions", "node.js", "npm", "grafana", "prometheus", "mlflow", "openssl", "esp-idf",
         "arduino", "llama.cpp", "pytorch", "ultralytics"]  # fmt: skip
GENERIC_SECURITY_FEEDS = ("CERT-FR",)
#: Fiabilité (grille-fiabilite.md, sur 7) par source ; 5 par défaut (seuil de rétention).
RELIABILITY = {
    "CNIL - actualités": 7,
    "CERT-FR - avis": 6,
    "CERT-FR - alertes": 6,
    "Hugging Face blog": 7,
    "Simon Willison": 7,
    "arXiv cs.CV": 5,
    "Hackaday": 5,
    "Arduino blog": 6,
}


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def themes_of(item: Item) -> list[str]:
    haystack = _plain(f"{item.title} {item.summary}")
    if item.feed.startswith(GENERIC_SECURITY_FEEDS) and not any(w in haystack for w in STACK):
        return []  # avis sur un produit que MicroForge n'utilise pas (Ivanti, Edge…)
    found = [t for t, words in THEMES.items() if any(w in haystack for w in words)]
    declared = [t for t in item.theme.split("/") if t in THEMES]
    return sorted(set(found) | set(declared))


def score(item: Item, now: datetime | None = None) -> float:
    """Pertinence (mots-clés du titre comptent double) + fiabilité + fraîcheur (≤ 7 jours)."""
    title, body = _plain(item.title), _plain(item.summary)
    hits = sum(
        (2 if w in title else 0) + (1 if w in body else 0)
        for words in THEMES.values()
        for w in words
    )
    reliability = RELIABILITY.get(item.feed, 6 if "releases" in item.feed.lower() else 5) / 7
    fresh = 0.0
    if item.published:
        age = (now or datetime.now(UTC)) - datetime.fromisoformat(item.published)
        fresh = max(0.0, 1 - age / timedelta(days=7))
    return round(min(hits, 6) + 2 * reliability + fresh, 3)


def select(
    items: list[Item], days: int = 7, per_theme: int = 5, now: datetime | None = None
) -> dict[str, list[Item]]:
    """Articles récents, dédoublonnés (lien ou titre), classés par thématique."""
    now = now or datetime.now(UTC)
    since = now - timedelta(days=days)
    seen: set[str] = set()
    keep: list[Item] = []
    for it in items:
        key = it.link or _plain(it.title)
        if key in seen:
            continue
        seen.add(key)
        if it.published and datetime.fromisoformat(it.published) < since:
            continue
        it.themes = themes_of(it)
        it.score = score(it, now)
        keep.append(it)
    by_theme: dict[str, list[Item]] = {t: [] for t in THEMES}
    for it in sorted(keep, key=lambda i: -i.score):
        for t in it.themes[:1]:  # une seule rubrique par article (la plus probable d'abord)
            if len(by_theme[t]) < per_theme:
                by_theme[t].append(it)
    return by_theme
