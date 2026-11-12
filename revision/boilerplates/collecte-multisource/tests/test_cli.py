"""Ligne de commande et envoi des fiches vers une API (simulée)."""

import json
import shutil
from pathlib import Path

import httpx

from collecte.__main__ import main
from collecte.modele import Fiche
from collecte.pipeline import envoyer

RACINE = Path(__file__).resolve().parents[1]


def test_ligne_de_commande(tmp_path: Path, monkeypatch):
    texte = (RACINE / "collecte/sources.toml").read_text(encoding="utf-8")
    config = tmp_path / "sources.toml"
    config.write_text(texte.replace('nom = "api"\n', 'nom = "api"\nactif = false\n'), encoding="utf-8")
    shutil.copytree(RACINE / "donnees_exemple", tmp_path / "donnees_exemple")
    monkeypatch.chdir(tmp_path)
    assert main(["--config", str(config), "--sortie", "sortie/gold.json"]) == 0
    fiches = json.loads((tmp_path / "sortie/gold.json").read_text(encoding="utf-8"))
    assert {"Dracula", "Nosferatu"} <= {f["titre"] for f in fiches}


def test_envoi_par_lots():
    recus: list[int] = []

    def api(requete: httpx.Request) -> httpx.Response:
        lot = json.loads(requete.content)
        recus.append(len(lot))
        return httpx.Response(200, json={"creees": len(lot), "mises_a_jour": 0})

    client = httpx.Client(base_url="http://donnees.test", transport=httpx.MockTransport(api))
    fiches = [Fiche(titre=f"Œuvre {i}") for i in range(5)]
    assert envoyer(fiches, client, taille_lot=2) == {"creees": 5, "mises_a_jour": 0}
    assert recus == [2, 2, 1]
