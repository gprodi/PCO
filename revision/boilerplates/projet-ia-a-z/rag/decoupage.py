"""Découpage des textes en passages : par phrases, avec recouvrement, sans couper un mot."""

import re

_PHRASES = re.compile(r"(?<=[.!?…])\s+")


def decouper(texte: str, taille: int = 600, recouvrement: int = 120) -> list[str]:
    """Passages d'au plus ``taille`` caractères (sauf phrase plus longue), qui se chevauchent."""
    phrases = [p.strip() for p in _PHRASES.split(texte or "") if p.strip()]
    passages: list[str] = []
    courant: list[str] = []
    for phrase in phrases:
        if courant and len(" ".join([*courant, phrase])) > taille:
            passages.append(" ".join(courant))
            # Reprend la fin du passage précédent (phrases entières) pour garder le contexte.
            reprise: list[str] = []
            for precedente in reversed(courant):
                if len(" ".join([precedente, *reprise])) > recouvrement:
                    break
                reprise.insert(0, precedente)
            courant = reprise
        courant.append(phrase)
    if courant:
        passages.append(" ".join(courant))
    return passages
