"""Briques : petits gabarits copier tirés du starter « projet-ia-a-z ».

Les fichiers partagés sont des copies exactes de ceux du starter (une seule version à maintenir) ;
chaque brique ajoute ses propres ``copier.yml``, README, ``pyproject.toml`` et tests.
``uv run python -m revision.briques`` recopie les fichiers ; un test vérifie qu'ils sont identiques.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from revision.config import PATHS

STARTER = "projet-ia-a-z"
PREFECT = "{% if avec_orchestration %}flux_prefect.py{% endif %}"
TEST_PREFECT = "{% if avec_orchestration %}test_flux_prefect.py{% endif %}"
EXEMPLES = [
    "donnees_exemple/catalogue.csv",
    "donnees_exemple/base_existante.sql",
    "donnees_exemple/gros_volume/partie-001.csv",
    "donnees_exemple/gros_volume/partie-002.csv",
]

#: brique → fichiers repris du starter
BRIQUES: dict[str, list[str]] = {
    "collecte-multisource": [
        "commun/__init__.py",
        "commun/config.py",
        "commun/logs.py",
        "collecte/__init__.py",
        "collecte/__main__.py",
        "collecte/modele.py",
        "collecte/normalise.py",
        "collecte/sources.py",
        "collecte/fusion.py",
        "collecte/pipeline.py",
        "collecte/sources.toml",
        "collecte/spark_job.py",
        f"collecte/{PREFECT}",
        *EXEMPLES,
        "tests/__init__.py",
        "tests/test_collecte.py",
        f"tests/{TEST_PREFECT}",
    ],
    "rag-llm-local": [
        "commun/__init__.py",
        "commun/config.py",
        "collecte/__init__.py",
        "collecte/normalise.py",
        "llm/__init__.py",
        "llm/passerelle.py",
        "rag/__init__.py",
        "rag/decoupage.py",
        "rag/embeddings.py",
        "rag/index.py",
        "rag/moteur.py",
        "rag/titres.py",
        "tests/__init__.py",
        "tests/faux.py",
        "tests/test_rag.py",
        "tests/test_llm.py",
    ],
}


def ecarts(racine: Path = PATHS.boilerplates) -> list[str]:
    """Fichiers de briques absents ou différents de ceux du starter."""
    sortie = []
    for brique, fichiers in BRIQUES.items():
        for chemin in fichiers:
            source, copie = racine / STARTER / chemin, racine / brique / chemin
            if not copie.exists() or copie.read_bytes() != source.read_bytes():
                sortie.append(f"{brique}/{chemin}")
    return sortie


def synchroniser(racine: Path = PATHS.boilerplates) -> list[str]:
    copies = ecarts(racine)
    for chemin in copies:
        brique, relatif = chemin.split("/", 1)
        cible = racine / brique / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(racine / STARTER / relatif, cible)
    return copies


if __name__ == "__main__":
    recopies = synchroniser()
    print("\n".join(recopies) or "Briques déjà à jour.")
    sys.exit(0)
