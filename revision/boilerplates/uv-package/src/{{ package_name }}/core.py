"""Fonctions du paquet."""

import re
import unicodedata


def slugify(text: str, sep: str = "-") -> str:
    """« Été à Lyon ! » -> « ete-a-lyon » : sans accents, minuscules, séparateur unique."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", sep, ascii_text.lower()).strip(sep)
