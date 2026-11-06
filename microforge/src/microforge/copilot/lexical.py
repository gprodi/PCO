"""Recherche par mots-clés (BM25) : repli du copilote quand aucun modèle d'embeddings n'est joignable.

Sans Ollama ni clé Gemini (cas d'une installation Docker sans profil « ai »), la recherche par
vecteurs est impossible ; le copilote répondait alors « 503 indisponible ». BM25 retrouve les
passages du catalogue qui partagent les mots de la question, pondérés par leur rareté : moins fin
que les vecteurs (pas de synonymes), mais sans aucun modèle et en quelques millisecondes.
"""

from __future__ import annotations

import math
from collections import Counter

from llm_gateway.vectorstore import Record

from microforge.core.catalog import normalize

#: Mots trop fréquents pour départager les passages (après normalisation : minuscules, sans accents).
STOP = frozenset(
    [
        "a",
        "au",
        "aux",
        "avec",
        "ce",
        "ces",
        "cet",
        "cette",
        "comment",
        "d",
        "dans",
        "de",
        "des",
        "du",
        "elle",
        "en",
        "est",
        "et",
        "il",
        "je",
        "l",
        "la",
        "le",
        "les",
        "leur",
        "ma",
        "mes",
        "mon",
        "ne",
        "nous",
        "on",
        "ou",
        "par",
        "pas",
        "plus",
        "pour",
        "qu",
        "quand",
        "que",
        "quel",
        "quelle",
        "quelles",
        "quels",
        "qui",
        "quoi",
        "sa",
        "sans",
        "se",
        "ses",
        "son",
        "sont",
        "sur",
        "ta",
        "tes",
        "ton",
        "tu",
        "un",
        "une",
        "vous",
        "y",
        "faut",
        "peut",
        "puis",
        "brancher",
        "utiliser",
    ]
)


def tokens(text: str) -> list[str]:
    return [t for t in normalize(text).split() if len(t) > 1 and t not in STOP]


class LexicalIndex:
    """Index BM25 en mémoire (k1 = 1,5, b = 0,75) ; le titre d'un passage compte double."""

    def __init__(self, records: list[Record], k1: float = 1.5, b: float = 0.75) -> None:
        self.records = records
        self.k1, self.b = k1, b
        self.docs = [Counter(tokens(f"{r.title} {r.title} {r.text}")) for r in records]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.lengths) / max(len(self.docs), 1)
        df = Counter(t for d in self.docs for t in d)
        n = len(records)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def __len__(self) -> int:
        return len(self.records)

    def search(
        self, query: str, k: int = 6, min_relative: float = 0.35
    ) -> list[tuple[float, Record]]:
        """Passages classés ; score ramené à [0, 1] par rapport au meilleur passage.

        Aucun mot de la question dans le catalogue -> liste vide (le copilote répond « je ne sais
        pas »). Les passages à moins de ``min_relative`` du meilleur sont écartés.
        """
        terms = {t for t in tokens(query) if t in self.idf}
        if not terms:
            return []
        scored = []
        for i, doc in enumerate(self.docs):
            norm = self.k1 * (1 - self.b + self.b * self.lengths[i] / self.avg)
            s = sum(
                self.idf[t] * doc[t] * (self.k1 + 1) / (doc[t] + norm) for t in terms if t in doc
            )
            if s > 0:
                scored.append((s, i))
        if not scored:
            return []
        scored.sort(key=lambda x: (-x[0], x[1]))
        top = scored[0][0]
        return [
            (round(s / top, 3), self.records[i]) for s, i in scored[:k] if s >= min_relative * top
        ]


def clip(text: str, max_chars: int) -> str:
    """Texte sur une ligne, coupé à un espace (jamais au milieu d'un mot)."""
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"


def best_lines(title: str, text: str, query: str, limit: int = 2, max_chars: int = 260) -> str:
    """Lignes d'un passage qui répondent à la question, pour la réponse sans modèle de langage.

    Les mots du titre du passage (« ESP32 DevKit V1 ») l'identifient sans rien répondre : ils sont
    ignorés pour choisir les lignes. Sans ligne pertinente, le début du passage.
    """
    wanted = set(tokens(query)) - set(tokens(title))
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    scored = [(len(wanted & set(tokens(ln))), i) for i, ln in enumerate(lines)]
    best = max((s for s, _ in scored), default=0)
    if best == 0:
        return clip(text, max_chars)
    keep = sorted(i for s, i in scored if s == best)[:limit]
    return clip(" · ".join(lines[i] for i in keep), max_chars)
