"""Collecte de bout en bout : ligne de commande, fichier « gold », import dans l'API de données."""

import shutil
from pathlib import Path

from collecte.__main__ import main
from collecte.pipeline import envoyer, executer, lire_config
from tests.faux import RACINE

EXEMPLES = RACINE / "donnees_exemple"


def test_ligne_de_commande_et_envoi(tmp_path: Path, monkeypatch, api_donnees):
    config = tmp_path / "sources.toml"
    texte = (RACINE / "collecte/sources.toml").read_text(encoding="utf-8")
    config.write_text(
        texte.replace('type = "api"\nnom = "api"', 'type = "api"\nnom = "api"\nactif = false'), encoding="utf-8"
    )
    shutil.copytree(EXEMPLES, tmp_path / "donnees_exemple")
    monkeypatch.chdir(tmp_path)
    sortie = tmp_path / "sortie" / "gold.json"
    assert main(["--config", str(config), "--sortie", str(sortie)]) == 0
    assert sortie.exists() and "Nosferatu" in sortie.read_text(encoding="utf-8")
    rapport = executer(lire_config(config), racine=tmp_path)
    # Dracula, Carmilla et Le Horla sont déjà en base (fixture) : mis à jour, pas dupliqués.
    assert envoyer(rapport.fiches, api_donnees, taille_lot=4) == {"creees": len(rapport.fiches) - 3, "mises_a_jour": 3}
    assert envoyer(rapport.fiches, api_donnees) == {"creees": 0, "mises_a_jour": len(rapport.fiches)}
