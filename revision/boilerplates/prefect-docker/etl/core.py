"""Extraction, nettoyage et chargement, sans dépendance à Prefect (facile à tester)."""

import sqlite3
from pathlib import Path

import httpx

API = "https://geo.api.gouv.fr/communes"


def fetch(departement: str, transport: httpx.BaseTransport | None = None) -> list[dict]:
    params = {"codeDepartement": departement, "fields": "nom,code,population,codesPostaux"}
    with httpx.Client(timeout=30, transport=transport) as client:
        r = client.get(API, params=params, headers={"User-Agent": "pipeline-pedagogique/1.0"})
        r.raise_for_status()
        return r.json()


def clean(rows: list[dict]) -> list[dict]:
    """Garde les communes complètes ; noms sans espaces superflus ; premier code postal."""
    out = {}
    for row in rows:
        code, nom = str(row.get("code", "")).strip(), " ".join(str(row.get("nom", "")).split())
        population = row.get("population")
        if not code or not nom or not isinstance(population, int) or population < 0:
            continue
        postaux = row.get("codesPostaux") or [""]
        out[code] = {"code": code, "nom": nom, "population": population, "code_postal": postaux[0]}
    return sorted(out.values(), key=lambda r: r["code"])


def save(rows: list[dict], db_path: str | Path) -> int:
    """Insère ou met à jour (clé : code INSEE) ; renvoie le nombre de lignes traitées."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS commune (code TEXT PRIMARY KEY, nom TEXT NOT NULL,"
            " population INTEGER NOT NULL, code_postal TEXT)"
        )
        conn.executemany(
            "INSERT INTO commune VALUES (:code, :nom, :population, :code_postal)"
            " ON CONFLICT(code) DO UPDATE SET nom = excluded.nom, population = excluded.population,"
            " code_postal = excluded.code_postal",
            rows,
        )
    return len(rows)
