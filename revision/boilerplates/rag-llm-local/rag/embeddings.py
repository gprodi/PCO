"""Vecteurs des textes : modèle d'embeddings (Ollama/Gemini via la passerelle) ou hachage hors ligne."""

import hashlib
import math
import re
from typing import Protocol

from collecte.normalise import cle_titre
from llm.passerelle import Passerelle

_MOTS = re.compile(r"[a-z0-9]+")


class Embeddeur(Protocol):
    nom: str

    def encoder(self, textes: list[str]) -> list[list[float]]: ...


def normer(vecteur: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in vecteur)) or 1.0
    return [x / n for x in vecteur]


class EmbeddeurHache:
    """Sac de mots et de paires de mots haché (sans modèle) : tests, démonstration hors ligne.

    Capte le vocabulaire commun, pas le sens : un vrai modèle (``EmbeddeurModele``) fait mieux.
    """

    nom = "hachage"

    def __init__(self, dimension: int = 512) -> None:
        self.dimension = dimension

    def _un(self, texte: str) -> list[float]:
        mots = _MOTS.findall(cle_titre(texte))
        vecteur = [0.0] * self.dimension
        for terme in [*mots, *(f"{a} {b}" for a, b in zip(mots, mots[1:], strict=False))]:
            h = int.from_bytes(hashlib.blake2b(terme.encode(), digest_size=8).digest(), "big")
            vecteur[h % self.dimension] += 1.0 if (h >> 63) & 1 else -1.0
        return normer(vecteur)

    def encoder(self, textes: list[str]) -> list[list[float]]:
        return [self._un(t) for t in textes]


class EmbeddeurModele:
    """Modèle d'embeddings servi par Ollama (bge-m3 par défaut) ; lève ``LLMIndisponible`` sinon."""

    def __init__(self, passerelle: Passerelle) -> None:
        self.passerelle = passerelle
        self.nom = passerelle.fournisseurs[0].modele_embed

    def encoder(self, textes: list[str]) -> list[list[float]]:
        return [normer(v) for v in self.passerelle.encoder(textes)]
