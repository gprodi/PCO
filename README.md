# PCO — projet de fin d'études « Développeur en IA » (Simplon, RNCP 37827)

[![ci](https://github.com/gprodi/PCO/actions/workflows/ci.yml/badge.svg?branch=claude/amazing-bohr-o38ndx)](https://github.com/gprodi/PCO/actions/workflows/ci.yml)

Ce dépôt réunit deux projets et les supports de l'année :

| Dossier | Contenu |
|---|---|
| [`microforge/`](microforge/README.md) | **MicroForge**, le projet de fin d'études : photo du stock de composants → inventaire par IA → projets réalisables → câblage, programme Arduino/ESP32/Pico, guide de soudure, simulation Wokwi, netlist KiCad, liste d'achat |
| [`revision/`](revision/) | **Révisions DevIA** : chaque cours devient fiche, QCM, flashcards espacées, exercices, carte mentale et podcast ; site statique + application locale |
| [`packages/llm_gateway/`](packages/llm_gateway/) | client IA commun : Ollama en local, repli Gemini (offre gratuite), profils matériel automatiques ; aucune API payante par défaut |
| [`referentiel/`](referentiel/) | référentiel RNCP 37827 (PDF), compétences C1–C21 structurées, modèles officiels des rapports E1–E5 |
| [`cours/`](cours/) | supports de cours de l'année |
| [`PLAN.md`](PLAN.md) | plan détaillé : sources de données, outils, épreuves E1–E5, feuille de route |

## MicroForge en chiffres

- 45 projets générables (domotique, sécurité, robots, lumière, musique, fêtes…) et 131 idées réparties en 17 thèmes ;
- 49 composants et 40 cartes en 11 familles (ESP32 classique/S2/S3/C3/C6/H2, ESP8266, Arduino Uno R3/R4, Nano, Mega, Leonardo, Nano Every, Nano 33, MKR, Due, Pico/Pico 2, STM32, Teensy) ;
- un parcours de progression en 7 étapes, de la première LED au robot autonome, et une vitrine de vrais projets open source (WLED, ESPHome, OpenBikeSensor, Otto, InMoov…).

### Ce qui est vérifié, et comment

| Vérification | Où |
|---|---|
| Allocation des broches et contrôle électrique, à chaque génération | `microforge/src/microforge/core/` |
| Syntaxe C++ des 131 firmwares (45 projets × familles compatibles) | `microforge/tests/test_core.py` (g++ + en-têtes Arduino simulés) |
| Compilation réelle avec arduino-cli sur AVR, ESP32 et RP2040 | job `firmware` de [la CI](.github/workflows/ci.yml) |
| Chaque projet renvoie vers des tutoriels publics du même montage | `microforge/src/microforge/core/data/references.yaml` |
| Montage sur du vrai matériel | **à faire** : champ `hardware_tested` de chaque modèle, à remplir après essai |

## Démarrer

Prérequis : [git](https://git-scm.com), [uv](https://docs.astral.sh/uv/) et [Node.js 22](https://nodejs.org). Optionnel : [Ollama](https://ollama.com) pour l'IA locale (gratuite, rien n'est envoyé en ligne).

```bash
git clone -b claude/amazing-bohr-o38ndx https://github.com/gprodi/PCO.git
```

```bash
cd PCO
```

```bash
uv sync --all-packages --group dev --extra data --extra app
```

### Révisions DevIA (outil de révision)

Une seule commande lance l'API locale et le site, puis ouvre http://localhost:4321/PCO/ (Windows, macOS, Linux) :

```bash
uv run revise start
```

`Ctrl+C` arrête tout. Le site, les QCM et les flashcards marchent sans IA ; le chat avec les cours, l'ajout de cours et l'oral blanc ont besoin d'Ollama et d'un modèle :

```bash
ollama pull qwen3:4b
```

Version en ligne, sans installation (lecture, QCM, flashcards) : le lien privé partagé par Claude. Autres commandes : `uv run revise --help`.

### Tests

```bash
uv run pytest
```

### MicroForge

Lancer MicroForge sans IA (réponses simulées), en trois terminaux :

```bash
LLM_CHAIN=fake uv run uvicorn microforge.api_data.main:app --port 8000
```

```bash
LLM_CHAIN=fake MF_API_DATA_URL=http://localhost:8000 uv run uvicorn microforge.api_ia.main:app --port 8001
```

```bash
cd microforge/src/microforge/app_streamlit && MF_API_DATA_URL=http://localhost:8000 MF_API_IA_URL=http://localhost:8001 uv run streamlit run Accueil.py
```

Avec Docker : `docker compose -f microforge/infra/compose.yml --profile core up`. Sur le Mac M4, lancer Ollama en application native (Docker n'a pas accès au GPU Apple). Détails par machine : [`microforge/README.md`](microforge/README.md).

Générer un projet en ligne de commande :

```bash
uv run microforge build robot-suiveur-ligne --board arduino-uno --out build/robot
```

## Rapports E1–E5

Les brouillons sont générés dans les modèles officiels : `microforge/docs/rapports/E<n>_MicroForge_brouillon.docx`. Les passages surlignés `[À COMPLÉTER]` attendent tes captures et mesures réelles. Pour régénérer après modification des fichiers `contenu_E<n>.yaml` :

```bash
uv run python microforge/docs/rapports/generer_rapports.py
```
