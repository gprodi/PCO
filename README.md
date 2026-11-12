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

- 145 projets générables, un pour chacune des 145 idées réparties en 17 thèmes (domotique, plantes, sécurité, robots, véhicules, lumière, musique, fêtes, animaux, cuisine, sciences, objets connectés…) ;
- 103 composants et 40 cartes en 11 familles (ESP32 classique/S2/S3/C3/C6/H2, ESP8266, Arduino Uno R3/R4, Nano, Mega, Leonardo, Nano Every, Nano 33, MKR, Due, Pico/Pico 2, STM32, Teensy) ;
- un copilote qui répond aux questions sur le matériel en citant le catalogue (379 passages indexés dans PostgreSQL + pgvector) ;
- un atelier virtuel : on branche chaque composant sur une broche de la carte (une erreur est expliquée), puis le projet tourne dans le navigateur (sa logique C++ traduite en JavaScript, un modèle de comportement par composant) ;
- un parcours de progression en 7 étapes, de la première LED au robot autonome, et une vitrine de vrais projets open source (WLED, ESPHome, OpenBikeSensor, Otto, InMoov…).

### Ce qui est vérifié, et comment

| Vérification | Où |
|---|---|
| Allocation des broches et contrôle électrique, à chaque génération | `microforge/src/microforge/core/` |
| Syntaxe C++ des 1 519 firmwares (145 projets × familles compatibles) | `microforge/tests/test_core.py` (g++ + en-têtes Arduino simulés) |
| Compilation réelle avec arduino-cli sur les 11 familles et les variantes de puce (ESP32-S3, C3, C6, H2, Pico 2 W) | job `firmware` de [la CI](.github/workflows/ci.yml) (16 jobs) |
| Copilote RAG : réponses citées, « je ne sais pas » sous le seuil, repli sans LLM, index PostgreSQL + pgvector | `microforge/tests/test_copilot.py`, job `pgvector` de la CI |
| Atelier virtuel : les 145 projets transpilés et exécutés 120 s virtuelles, capteurs sollicités, sans erreur ; sémantique du C (division entière, débordements) ; erreurs de branchement expliquées ; page testée dans Chromium | `microforge/tests/test_sim.py` |
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

Le chat cite ses sources : il cherche dans un index sémantique des 36 fiches rédigées (notions, points clés, pièges, exercices corrigés, QCM, flashcards : 829 passages) et des supports ingérés (`uv run revise ingest`). Construire l'index une fois (modèle d'embeddings multilingue) :

```bash
ollama pull bge-m3
```

```bash
uv run revise index
```

Par défaut l'index est un fichier JSON local. Pour le placer dans **PostgreSQL + pgvector** (index HNSW en distance cosinus, partagé entre machines ou avec l'API en conteneur) :

```bash
docker run -d --name revision-pg -e POSTGRES_PASSWORD=revision -p 127.0.0.1:5433:5432 pgvector/pgvector:pg17
```

```bash
uv sync --all-packages --extra pgvector
```

```bash
REVISION_VECTOR_URL=postgresql+psycopg://postgres:revision@127.0.0.1:5433/postgres uv run revise index
```

La même variable `REVISION_VECTOR_URL` doit être définie dans le terminal qui lance `revise start` (le chat interroge alors PostgreSQL).

Version en ligne, sans installation (lecture, QCM, flashcards) : le lien privé partagé par Claude. Autres commandes : `uv run revise --help`.

#### Boilerplates (gabarits copier)

Douze gabarits de projet, rédigés à partir des cours et reliés aux compétences du référentiel
(page « Boilerplates » du site) :

- **`projet-ia-a-z`**, le starter complet du fil rouge HorRAGor : collecte depuis cinq types de
  sources et fusion, base derrière sa propre API sur un réseau Docker privé, RAG (pgvector ou
  mémoire, repli BM25), graphe multi-agent LangGraph (chercheur, enquêteur web, narrateur, juge)
  tracé par Langfuse, API d'IA à jetons de rafraîchissement à rotation, chat Streamlit,
  Prometheus/Grafana/Uptime Kuma, CI avec couverture ≥ 80 %, Sphinx. Options : Prefect,
  supervision, CI, documentation. Aucune API payante (Ollama, Gemini gratuit en secours).
- Deux briques tirées du starter, utilisables seules : **`collecte-multisource`** (bloc E1) et
  **`rag-llm-local`** (passerelle LLM et RAG).
- Neuf gabarits ciblés : API FastAPI sécurisée (JWT à rotation, Argon2id), deux API + Streamlit,
  Streamlit multipage, registre MLflow avec alias, pipeline Prefect, CI/CD GitHub Actions,
  supervision Prometheus/Grafana/Uptime Kuma, journaux Loki/Alloy, paquet uv.

Pour en créer un projet (les questions, nom et options, sont posées au lancement) :

```bash
uvx copier copy revision/boilerplates/projet-ia-a-z mon-projet
```

Chaque gabarit est rendu, puis ses propres tests, `ruff check` et `ruff format --check` passent
dans la CI (`revision/tests/test_boilerplates.py`) ; le starter l'est aussi sans ses options. Les
briques reprennent les fichiers du starter à l'identique (`uv run python -m revision.briques`).

### Tests

```bash
uv run pytest
```

### MicroForge

Lancer MicroForge sans IA (réponses simulées), en quatre terminaux :

```bash
LLM_CHAIN=fake uv run uvicorn microforge.api_data.main:app --port 8000
```

```bash
LLM_CHAIN=fake MF_API_DATA_URL=http://localhost:8000 uv run uvicorn microforge.api_ia.main:app --port 8001
```

```bash
cd microforge/src/microforge/app_streamlit && MF_API_DATA_URL=http://localhost:8000 MF_API_IA_URL=http://localhost:8001 uv run streamlit run Accueil.py
```

```bash
cd microforge/pwa && npm ci && npm run dev
```

La PWA est sur http://localhost:5173, la preuve de concept Streamlit sur http://localhost:8501.

#### Avec Docker (Windows, Mac ou Linux)

Prérequis : Docker Desktop démarré (« Engine running ») et Docker Compose v2.24 ou plus
(`docker compose version`). Toutes les commandes se tapent depuis la racine du dépôt (le
dossier `PCO`). Tant que la PR n'est pas fusionnée dans `main`, le travail récent est sur la branche
`claude/amazing-bohr-o38ndx` :

```bash
git fetch origin
```

```bash
git switch claude/amazing-bohr-o38ndx
```

```bash
git pull
```

Puis, toujours depuis la racine :

```bash
docker compose -f microforge/infra/docker-compose.yml --profile core up -d --build
```

La première construction prend plusieurs minutes (4 images). Ensuite :

| Interface | Adresse |
|---|---|
| Application (PWA) | http://localhost:5173 |
| Preuve de concept Streamlit | http://localhost:8501 |
| API données / API IA (documentation interactive) | http://localhost:8000/docs · http://localhost:8001/docs |

État des services :

```bash
docker compose -f microforge/infra/docker-compose.yml --profile core ps
```

Arrêt :

```bash
docker compose -f microforge/infra/docker-compose.yml --profile core down
```

Vérifier que tout fonctionne (avec la supervision : ajouter `--profile monitoring` à la commande
`up`) ; une ligne OK ou ÉCHEC par contrôle :

```bash
uv run python microforge/infra/verifier_pile.py
```

**Si la commande `up` échoue** (messages relevés sous Windows, Git Bash) :

| Message | Cause | Remède |
|---|---|---|
| `failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine` | Docker Desktop n'est pas lancé | lancer Docker Desktop, attendre « Engine running », vérifier avec `docker info` |
| `unknown flag: --profile` (suivi de l'aide de `docker`) | `docker` ne transmet pas l'option à Compose (vu sous Git Bash avec Docker Desktop et Compose v5.6.1, alors que `docker compose version` répondait) | **taper `docker-compose` (avec un tiret) au lieu de `docker compose`**, mêmes options : `docker-compose --profile core up -d --build` (c'est ce qui a marché). Sinon : `docker compose version` doit afficher v2.24 ou plus, et `which -a docker` (Git Bash) ou `where docker` (PowerShell) montrer celui de Docker Desktop en premier |

Aucun fichier `.env` n'est nécessaire : les valeurs de développement de `microforge/.env.example`
servent par défaut. Pour en changer (clé Gemini, mot de passe PostgreSQL…), copier ce fichier en
`microforge/.env` et le modifier : ses valeurs l'emportent.

**Port déjà pris** (un autre projet sur 8000, par exemple ; message « port is already allocated »,
ou la PWA affiche « Impossible de joindre l'API ») : créer le fichier `microforge/infra/.env` avec
les ports voulus, puis relancer la commande `up`. La PWA et les origines autorisées suivent :

```
MF_API_DATA_PORT=8010
MF_API_IA_PORT=8011
```

Variables disponibles : `MF_API_DATA_PORT` (8000), `MF_API_IA_PORT` (8001), `MF_PWA_PORT` (5173),
`MF_STREAMLIT_PORT` (8501). Pour savoir quel programme occupe un port sous Windows (PowerShell) :
`Get-Process -Id (Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess` ; sous Mac ou
Linux : `lsof -i :8000`. Sans Ollama (ni clé Gemini), la génération des projets
fonctionne (moteur déterministe) et le copilote cherche par mots-clés et cite les lignes du catalogue
qui répondent (vérifié sur la pile Docker le 06/11/2026) ; la reconnaissance
des composants sur photo, elle, a besoin d'Ollama ou d'un modèle entraîné. Sur le Mac M4, lancer Ollama en application native (Docker n'a pas accès
au GPU Apple). Détails par machine : [`microforge/README.md`](microforge/README.md).

Générer un projet en ligne de commande :

```bash
uv run microforge build robot-suiveur-ligne --board arduino-uno --out build/robot
```

## Rapports E1–E5

Les brouillons sont générés dans les modèles officiels : `microforge/docs/rapports/E<n>_MicroForge_brouillon.docx`. Les passages surlignés `[À COMPLÉTER]` attendent tes captures et mesures réelles. Pour régénérer après modification des fichiers `contenu_E<n>.yaml` :

```bash
uv run python microforge/docs/rapports/generer_rapports.py
```
