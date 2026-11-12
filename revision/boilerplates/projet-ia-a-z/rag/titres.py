"""Index des titres en mémoire : le « routeur » qui reconnaît l'œuvre dont parle une question.

Rôle de l'index FAISS [titre : identifiant] du cours ; les titres sont courts, une comparaison
approximative (RapidFuzz) tolère les fautes de frappe sans modèle ni dépendance de plus.
"""

import re
from collections.abc import Iterable

from rapidfuzz import fuzz, process

from collecte.normalise import cle_titre

_SOUS_TITRE = re.compile(r"\s+ou\s+|\s+or\s+|\s*[:;(—–]\s*|\s+-\s+", re.IGNORECASE)


class IndexTitres:
    def __init__(self, oeuvres: Iterable[tuple[int, str]] = ()) -> None:
        self.titres: dict[int, str] = {}
        #: (identifiant, variante) → clé de comparaison ; variante 1 = titre sans sous-titre
        self.cles: dict[tuple[int, int], str] = {}
        self.ajouter(oeuvres)

    def __len__(self) -> int:
        return len(self.titres)

    def ajouter(self, oeuvres: Iterable[tuple[int, str]]) -> None:
        for oeuvre_id, titre in oeuvres:
            self.titres[oeuvre_id] = titre
            self.cles[(oeuvre_id, 0)] = cle_titre(titre)
            # « Frankenstein ou le Prométhée moderne » se cite souvent « Frankenstein » : titre court en plus.
            court = cle_titre(_SOUS_TITRE.split(titre, maxsplit=1)[0])
            if court != self.cles[(oeuvre_id, 0)] and len(court) >= 5:
                self.cles[(oeuvre_id, 1)] = court

    def trouver(self, texte: str, seuil: float = 85) -> tuple[int, str, float] | None:
        """L'œuvre citée dans ``texte`` (le titre le plus long à score égal), ou None."""
        question = cle_titre(texte)
        mots = set(question.split())
        candidats = []
        for valeur, score, (oeuvre_id, _) in process.extract(
            question, self.cles, scorer=fuzz.partial_ratio, score_cutoff=seuil, limit=10
        ):
            # Titre très court (« Emma ») : exiger le mot entier, sinon trop de faux positifs.
            if len(valeur) < 5 and valeur not in mots:
                continue
            candidats.append((score, len(valeur), oeuvre_id))
        if not candidats:
            return None
        score, _, oeuvre_id = max(candidats)
        return oeuvre_id, self.titres[oeuvre_id], score
