"""Fusion et réconciliation (MDM) : une fiche par œuvre, chaque champ pris à la source la plus fiable.

Rapprochement, dans l'ordre :
1. identifiant externe commun (même espace : ``ref_catalogue``, ``imdb``…) ;
2. titre proche (similarité de Levenshtein normalisée, RapidFuzz) et année à un an près.
Un champ vide est complété par la source suivante dans l'ordre de priorité.
"""

from collections import defaultdict
from collections.abc import Iterable

from rapidfuzz import fuzz

from collecte.modele import Enregistrement, Fiche
from collecte.normalise import cle_titre, dans_le_theme

CHAMPS = ("titre", "annee", "auteur", "genre", "resume", "note")


class Fusion:
    def __init__(self, priorite: list[str], seuil_titre: float = 88) -> None:
        self.priorite = {source: rang for rang, source in enumerate(priorite)}
        self.seuil = seuil_titre
        self.fiches: list[Fiche] = []
        self._par_id: dict[tuple[str, str], Fiche] = {}
        self._par_annee: dict[int | None, list[Fiche]] = defaultdict(list)

    def rang(self, enregistrement: Enregistrement) -> int:
        return self.priorite.get(enregistrement.source, len(self.priorite))

    def _retrouver(self, e: Enregistrement) -> Fiche | None:
        for cle in e.ids.items():
            if cle in self._par_id:
                return self._par_id[cle]
        cle = cle_titre(e.titre)
        annees = [None] if e.annee is None else [e.annee - 1, e.annee, e.annee + 1, None]
        meilleure, score_max = None, self.seuil
        for annee in annees:
            for fiche in self._par_annee.get(annee, []):
                score = fuzz.ratio(cle, cle_titre(fiche.titre))
                if score >= score_max:
                    meilleure, score_max = fiche, score
        return meilleure

    def ajouter(self, e: Enregistrement) -> Fiche:
        fiche = self._retrouver(e)
        if fiche is None:
            fiche = Fiche(titre=e.titre)
            self.fiches.append(fiche)
        avant = fiche.annee
        for champ in CHAMPS:
            valeur = getattr(e, champ)
            if valeur is not None and (champ not in fiche.provenance):
                setattr(fiche, champ, valeur)
                fiche.provenance[champ] = e.source
        for cle, valeur in e.ids.items():
            fiche.ids.setdefault(cle, valeur)
            self._par_id[(cle, valeur)] = fiche
        if e.source not in fiche.sources:
            fiche.sources.append(e.source)
        # Rangement par année (comparaison par identité : deux fiches peuvent être égales champ à champ).
        ancien = self._par_annee[avant]
        if avant != fiche.annee:
            ancien[:] = [f for f in ancien if f is not fiche]
        if not any(f is fiche for f in self._par_annee[fiche.annee]):
            self._par_annee[fiche.annee].append(fiche)
        return fiche


def fusionner(
    enregistrements: Iterable[Enregistrement],
    priorite: list[str],
    seuil_titre: float = 88,
    genres: set[str] | None = None,
) -> tuple[list[Fiche], int]:
    """Renvoie (fiches gardées, nombre de fiches écartées par le filtre thématique)."""
    fusion = Fusion(priorite, seuil_titre)
    for e in sorted(enregistrements, key=fusion.rang):
        fusion.ajouter(e)
    if genres is None:
        return fusion.fiches, 0
    gardees = [f for f in fusion.fiches if dans_le_theme(f.genre, genres)]
    return gardees, len(fusion.fiches) - len(gardees)
