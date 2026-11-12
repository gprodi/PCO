"""Homogénéisation des formats : textes, titres, dates ISO 8601, notes sur 10."""

import html
import re
import unicodedata
from datetime import date

_BALISES = re.compile(r"<[^>]+>")
_ESPACES = re.compile(r"\s+")
_ARTICLES = {"the", "a", "an", "le", "la", "les", "l", "un", "une"}
_ANNEE = re.compile(r"^(\d{4})$")
_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})")
_FR = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")


def texte(valeur: object) -> str | None:
    """Retire les balises HTML et les entités, normalise l'Unicode (NFC) et les espaces."""
    if valeur is None:
        return None
    propre = html.unescape(_BALISES.sub(" ", str(valeur)))
    propre = _ESPACES.sub(" ", unicodedata.normalize("NFC", propre)).strip()
    return propre or None


def cle_titre(titre: str) -> str:
    """Forme de comparaison : minuscules, sans accents ni ponctuation, sans article initial."""
    sans_accents = unicodedata.normalize("NFKD", titre.lower())
    sans_accents = "".join(c for c in sans_accents if not unicodedata.combining(c))
    mots = re.sub(r"[^a-z0-9]+", " ", sans_accents).split()
    if len(mots) > 1 and mots[0] in _ARTICLES:
        mots = mots[1:]
    return " ".join(mots)


def date_iso(valeur: object) -> str | None:
    """« 1897 », 1897, « 1897-05-26 », « 26/05/1897 » → « AAAA-MM-JJ » (année seule : 1er janvier)."""
    if valeur is None or valeur == "":
        return None
    brut = str(valeur).strip()
    if isinstance(valeur, float) and valeur.is_integer():
        brut = str(int(valeur))
    try:
        if m := _ANNEE.match(brut):
            return date(int(m[1]), 1, 1).isoformat()
        if m := _ISO.match(brut):
            return date(int(m[1]), int(m[2]), int(m[3])).isoformat()
        if m := _FR.match(brut):
            return date(int(m[3]), int(m[2]), int(m[1])).isoformat()
    except ValueError:
        return None
    return None


def annee(valeur: object) -> int | None:
    iso = date_iso(valeur)
    return int(iso[:4]) if iso else None


def note_sur_10(valeur: object, echelle: float = 10) -> float | None:
    """Ramène une note sur 10 (« 87 » sur 100 → 8.7) ; hors bornes ou illisible → None."""
    if valeur is None or valeur == "":
        return None
    try:
        brute = float(str(valeur).replace(",", ".").rstrip("%"))
    except ValueError:
        return None
    note = brute * 10 / echelle
    return round(note, 1) if 0 <= note <= 10 else None


def dans_le_theme(genre: str | None, genres: set[str]) -> bool:
    """Filtrage thématique strict : le genre doit contenir l'un des mots-clés (sans accents)."""
    if not genre:
        return False
    cle = cle_titre(genre)
    return any(cle_titre(g) in cle for g in genres)
