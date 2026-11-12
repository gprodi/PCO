"""Collecte complète : sources de ``sources.toml`` → fusion → filtre → fichier « gold » ou API de données.

Une source en échec est signalée dans le rapport sans arrêter les autres.
"""

import json
import sqlite3
import tomllib
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from collecte import sources
from collecte.fusion import fusionner
from collecte.modele import Enregistrement, Fiche

CONFIG = Path(__file__).with_name("sources.toml")


@dataclass
class Rapport:
    fiches: list[Fiche]
    par_source: dict[str, int | str] = field(default_factory=dict)
    ecartees: int = 0

    def resume(self) -> str:
        lignes = [f"- {nom} : {etat}" for nom, etat in self.par_source.items()]
        lignes.append(f"{len(self.fiches)} fiches gardées, {self.ecartees} hors thème écartées")
        return "\n".join(lignes)


def lire_config(chemin: Path = CONFIG) -> dict[str, Any]:
    return tomllib.loads(chemin.read_text(encoding="utf-8"))


def preparer_sqlite(url: str, script: Path) -> None:
    """Crée la base SQLite d'exemple depuis son script SQL si elle n'existe pas encore."""
    chemin = Path(url.removeprefix("sqlite:///"))
    if url.startswith("sqlite:///") and not chemin.exists():
        chemin.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(chemin)) as connexion:
            connexion.executescript(script.read_text(encoding="utf-8"))
            connexion.commit()


def extraire(source: dict[str, Any], client: httpx.Client, racine: Path, agent: str) -> list[Enregistrement]:
    """Lance l'extracteur correspondant au ``type`` d'une entrée de ``sources.toml``."""
    commun = {"source": source["nom"], "echelle_note": source.get("echelle_note", 10)}
    genre = source.get("genre_par_defaut")
    match source["type"]:
        case "api":
            return sources.depuis_api(
                client, source["url"], source["champs"], params=source.get("params"),
                liste=source.get("liste", "results"), pages=source.get("pages", 1),
                genre_par_defaut=genre, **commun,
            )  # fmt: skip
        case "web":
            return sources.depuis_page_web(
                client, source["url"], source["selecteurs"], agent=agent, genre_par_defaut=genre, **commun
            )
        case "csv":
            return sources.depuis_csv(
                racine / source["chemin"], source["colonnes"], separateur=source.get("separateur", ","),
                genre_par_defaut=genre, **commun,
            )  # fmt: skip
        case "sql":
            url = source["url"].replace("{racine}", racine.as_posix())
            if "script" in source:
                preparer_sqlite(url, racine / source["script"])
            return sources.depuis_sql(
                url, source["requete"], params=source.get("params"), genre_par_defaut=genre, **commun
            )
        case "gros_volume":
            return sources.depuis_gros_volume(
                (racine / source["motif"]).as_posix(), source["colonnes"], genres=source["genres"],
                colonne_genre=source.get("colonne_genre", "genres"), moteur=source.get("moteur", "polars"), **commun,
            )  # fmt: skip
    raise ValueError(f"type de source inconnu : {source['type']}")


def executer(
    config: dict[str, Any], client: httpx.Client | None = None, racine: Path = Path(), agent: str = "assistant-ia"
) -> Rapport:
    client = client or httpx.Client(timeout=30, headers={"User-Agent": agent}, follow_redirects=True)
    tout: list[Enregistrement] = []
    par_source: dict[str, int | str] = {}
    for source in config.get("source", []):
        if not source.get("actif", True):
            par_source[source["nom"]] = "désactivée"
            continue
        try:
            lot = extraire(source, client, racine, agent)
        except Exception as erreur:  # une source en panne ne bloque pas les autres
            logger.error("{} : échec ({})", source["nom"], erreur)
            par_source[source["nom"]] = f"échec : {type(erreur).__name__}"
            continue
        par_source[source["nom"]] = len(lot)
        tout += lot
    reglages = config.get("fusion", {})
    fiches, ecartees = fusionner(
        tout,
        reglages.get("priorite", []),
        reglages.get("seuil_titre", 88),
        set(reglages["genres"]) if "genres" in reglages else None,
    )
    return Rapport(fiches, par_source, ecartees)


def ecrire(fiches: list[Fiche], chemin: Path) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps([f.model_dump() for f in fiches], ensure_ascii=False, indent=1), encoding="utf-8")


def envoyer(fiches: list[Fiche], client: httpx.Client, taille_lot: int = 500) -> dict[str, int]:
    """Envoie les fiches à l'API de données (``POST /oeuvres/import``), par lots."""
    total = {"creees": 0, "mises_a_jour": 0}
    for debut in range(0, len(fiches), taille_lot):
        lot = [f.model_dump() for f in fiches[debut : debut + taille_lot]]
        reponse = client.post("/oeuvres/import", json=lot)
        reponse.raise_for_status()
        for cle in total:
            total[cle] += reponse.json()[cle]
    return total
