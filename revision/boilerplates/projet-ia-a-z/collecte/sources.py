"""Les cinq types de sources (bloc E1). Chaque extracteur renvoie des ``Enregistrement`` normalisés.

1. API REST (``depuis_api``)          — JSON paginé, reprises sur 429/503 avec ``Retry-After``
2. Page web (``depuis_page_web``)     — robots.txt vérifié, sélecteurs CSS (BeautifulSoup)
3. Fichier CSV (``depuis_csv``)       — Polars, doublons titre + année retirés
4. Base SQL (``depuis_sql``)          — requête paramétrée (aucune concaténation de chaînes)
5. Gros volume (``depuis_gros_volume``) — fichiers découpés lus en flux (Polars) ou par Spark
"""

import time
from collections.abc import Callable, Iterable
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
import polars as pl
from bs4 import BeautifulSoup
from loguru import logger
from sqlalchemy import create_engine, text

from collecte import normalise
from collecte.modele import Enregistrement

#: champs d'``Enregistrement`` qu'une correspondance de colonnes peut viser ;
#: « id:<nom> » range la valeur dans ``ids[<nom>]``
CHAMPS = {"titre", "annee", "auteur", "genre", "resume", "note", "url"}


class SourceInterdite(Exception):
    """robots.txt interdit la page : on ne la collecte pas."""


def enregistrement(source: str, brut: dict[str, Any], echelle_note: float = 10) -> Enregistrement | None:
    """Normalise un dictionnaire déjà renommé (titre, annee, …, id:xxx) ; sans titre → None."""
    titre = normalise.texte(brut.get("titre"))
    if not titre:
        return None
    ids = {cle[3:]: str(v) for cle, v in brut.items() if cle.startswith("id:") and v not in (None, "")}
    return Enregistrement(
        source=source,
        titre=titre,
        annee=normalise.annee(brut.get("annee")),
        auteur=normalise.texte(brut.get("auteur")),
        genre=normalise.texte(brut.get("genre")),
        resume=normalise.texte(brut.get("resume")),
        note=normalise.note_sur_10(brut.get("note"), echelle_note),
        ids=ids,
        url=brut.get("url"),
    )


def _valeur(objet: Any, chemin: str) -> Any:
    """Suit « a.b.c » dans un JSON ; une liste rencontrée en route donne son premier élément."""
    for morceau in chemin.split("."):
        if isinstance(objet, list):
            objet = objet[0] if objet else None
        if not isinstance(objet, dict):
            return None
        objet = objet.get(morceau)
    if isinstance(objet, list):
        return objet[0] if objet else None
    return objet


def _attente(reponse: httpx.Response, essai: int) -> float:
    """Délai demandé par le serveur (secondes ou date HTTP), sinon attente exponentielle."""
    valeur = reponse.headers.get("Retry-After")
    if valeur:
        try:
            return float(valeur)
        except ValueError:
            try:
                return max(0.0, parsedate_to_datetime(valeur).timestamp() - time.time())
            except (TypeError, ValueError):
                pass
    return float(2**essai)


def obtenir(
    client: httpx.Client,
    url: str,
    params: dict[str, Any] | None = None,
    essais: int = 3,
    pause: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    """GET avec reprises sur 429 et 503 (au plus 30 s d'attente par reprise)."""
    for essai in range(essais):
        reponse = client.get(url, params=params)
        if reponse.status_code in (429, 503) and essai < essais - 1:
            delai = min(_attente(reponse, essai), 30.0)
            logger.warning("{} : {} — nouvel essai dans {:.0f} s", url, reponse.status_code, delai)
            pause(delai)
            continue
        reponse.raise_for_status()
        return reponse
    raise AssertionError("inaccessible")  # pragma: no cover


def depuis_api(
    client: httpx.Client,
    url: str,
    champs: dict[str, str],
    *,
    source: str = "api",
    params: dict[str, Any] | None = None,
    liste: str = "results",
    param_page: str = "page",
    pages: int = 1,
    genre_par_defaut: str | None = None,
    echelle_note: float = 10,
    pause: Callable[[float], None] = time.sleep,
) -> list[Enregistrement]:
    """API JSON paginée ; ``champs`` associe un champ (ou « id:nom ») à un chemin JSON."""
    sortie: list[Enregistrement] = []
    for page in range(1, pages + 1):
        donnees = obtenir(client, url, {**(params or {}), param_page: page}, pause=pause).json()
        elements = _liste(donnees, liste)
        if not elements:
            break
        lignes = [{cible: _valeur(e, chemin) for cible, chemin in champs.items()} for e in elements]
        sortie += _depuis_lignes(lignes, source, genre_par_defaut, echelle_note, journal=False)
    logger.info("{} : {} enregistrements", source, len(sortie))
    return sortie


def _liste(donnees: Any, chemin: str) -> list[Any]:
    """La liste d'éléments d'une réponse JSON (« docs », « data.items »… ; vide : la racine)."""
    objet = donnees
    for morceau in chemin.split(".") if chemin else []:
        objet = objet.get(morceau) if isinstance(objet, dict) else None
    return objet if isinstance(objet, list) else []


def autorise_par_robots(client: httpx.Client, url: str, agent: str) -> bool:
    """Lit /robots.txt du site ; absent (404) → autorisé, illisible (5xx) → interdit par prudence."""
    morceaux = urlsplit(url)
    reponse = client.get(f"{morceaux.scheme}://{morceaux.netloc}/robots.txt")
    if reponse.status_code in (401, 403) or reponse.status_code >= 500:
        return False
    if reponse.status_code >= 400:
        return True
    lecteur = RobotFileParser()
    lecteur.parse(reponse.text.splitlines())
    return lecteur.can_fetch(agent, url)


def depuis_page_web(
    client: httpx.Client,
    url: str,
    selecteurs: dict[str, str],
    *,
    source: str = "web",
    agent: str = "assistant-ia",
    genre_par_defaut: str | None = None,
    echelle_note: float = 10,
) -> list[Enregistrement]:
    """Page HTML statique : ``selecteurs["ligne"]`` désigne chaque œuvre, les autres clés ses champs.

    Pages construites en JavaScript : passer par Playwright ou Selenium (README).
    """
    if not autorise_par_robots(client, url, agent):
        raise SourceInterdite(f"robots.txt interdit {url}")
    page = BeautifulSoup(obtenir(client, url).text, "html.parser")
    lignes = []
    for ligne in page.select(selecteurs["ligne"]):
        brut: dict[str, Any] = {}
        for cible, selecteur in selecteurs.items():
            noeud = ligne.select_one(selecteur) if cible != "ligne" else None
            if noeud is not None:
                brut[cible] = noeud.get("href") if cible == "url" else noeud.get_text(" ", strip=True)
        lignes.append(brut)
    return _depuis_lignes(lignes, source, genre_par_defaut, echelle_note)


def _depuis_lignes(
    lignes: Iterable[dict[str, Any]],
    source: str,
    genre_par_defaut: str | None,
    echelle_note: float,
    journal: bool = True,
) -> list[Enregistrement]:
    sortie = []
    for brut in lignes:
        brut["genre"] = brut.get("genre") or genre_par_defaut
        if (fiche := enregistrement(source, brut, echelle_note)) is not None:
            sortie.append(fiche)
    if journal:
        logger.info("{} : {} enregistrements", source, len(sortie))
    return sortie


def depuis_csv(
    chemin: str | Path,
    colonnes: dict[str, str],
    *,
    source: str = "csv",
    separateur: str = ",",
    genre_par_defaut: str | None = None,
    echelle_note: float = 10,
) -> list[Enregistrement]:
    """CSV lu par Polars ; ``colonnes`` associe un champ à une colonne du fichier."""
    table = pl.read_csv(chemin, separator=separateur, infer_schema_length=0)
    table = table.select([pl.col(col).alias(cible) for cible, col in colonnes.items()])
    if {"titre", "annee"} <= set(table.columns):
        table = table.unique(subset=["titre", "annee"], keep="first", maintain_order=True)
    return _depuis_lignes(table.iter_rows(named=True), source, genre_par_defaut, echelle_note)


def depuis_sql(
    url: str,
    requete: str,
    *,
    params: dict[str, Any] | None = None,
    source: str = "sql",
    genre_par_defaut: str | None = None,
    echelle_note: float = 10,
) -> list[Enregistrement]:
    """Requête SQL paramétrée (``:nom``) ; ses colonnes portent déjà les noms des champs."""
    moteur = create_engine(url)
    try:
        with moteur.connect() as connexion:
            lignes = [dict(r) for r in connexion.execute(text(requete), params or {}).mappings()]
    finally:
        moteur.dispose()
    return _depuis_lignes(lignes, source, genre_par_defaut, echelle_note)


def depuis_gros_volume(
    motif: str,
    colonnes: dict[str, str],
    *,
    genres: Iterable[str],
    source: str = "gros_volume",
    colonne_genre: str = "genres",
    moteur: str = "polars",
    echelle_note: float = 10,
) -> list[Enregistrement]:
    """Fichiers CSV découpés (motif glob) : filtrage par genre et dédoublonnage hors mémoire.

    ``moteur="polars"`` : lecture paresseuse en flux ; ``moteur="spark"`` : ``collecte.spark_job``.
    """
    genres = [g.lower() for g in genres]
    if moteur == "spark":
        from collecte.spark_job import agreger, session_locale

        spark = session_locale()
        try:
            lignes = agreger(spark, motif, colonnes, genres, colonne_genre)
        finally:
            spark.stop()
    else:
        motif_genre = "|".join(genres)
        requete = (
            pl.scan_csv(motif, infer_schema_length=0)
            .filter(pl.col(colonne_genre).str.to_lowercase().str.contains(motif_genre))
            .select([pl.col(col).alias(cible) for cible, col in colonnes.items()])
        )
        if {"titre", "annee"} <= set(colonnes):
            requete = requete.unique(subset=["titre", "annee"], keep="first", maintain_order=True)
        lignes = requete.collect(engine="streaming").to_dicts()
    return _depuis_lignes(lignes, source, None, echelle_note)
