# Plan détaillé — MicroForge (projet de fin d'études) + Révisions DevIA

> Dépôt `gprodi/PCO` — branche de travail `claude/amazing-bohr-o38ndx` — rédigé le 02/11/2026

---

## 0. Contexte

Le dépôt contient :
- ~45 supports de l'année Simplon « Développeur en IA » (formateur Antony Schutz, GitHub DeVerMyst, 81 dépôts publics) ;
- sur `origin/main` (commit `72e6e83`), le référentiel **RNCP37827** : `IA-E1.pdf`, `IA-E2-E3.pdf`,
  `IA-E4-E5.pdf`, `E12345-E1.pdf`, `RNCP37827.pdf`, plus `HorRAGor BOT Partie 2/3.md`.

Deux livrables sont attendus :
1. **MicroForge** (prioritaire), le projet de fin d'études. C'est une app d'aide pour ESP32, Arduino, RP2040 et autres :
   1. on photographie son stock et l'IA le reconnaît pour en faire un inventaire ;
   2. l'app propose des montages réalisables avec ce stock ;
   3. pour chaque montage, elle génère le schéma de câblage et le guide de soudure, le firmware, une simulation, un flash USB et une netlist KiCad ;
   4. le mode « je veux construire X » donne la liste d'achat chiffrée, les plans et le code.

   Le projet sert de support aux **5 épreuves E1 à E5 (C1 à C21)**, avec une soutenance dans plus de 4 mois.
2. **Révisions DevIA**, un « NotebookLM amélioré » :
   - chaque cours est digéré automatiquement en fiche, QCM, exercices, flashcards espacées, carte mentale et podcast ;
   - s'y ajoutent des boilerplates, un chat avec les cours et une préparation aux épreuves E1 à E5 ;
   - forme : app locale + site publié.

### Décisions validées
| Sujet | Décision |
|---|---|
| Front MicroForge | Streamlit pour la preuve de concept, puis PWA React mobile |
| Vision | Hybride : détecteur YOLO entraîné par Gaël + VLM pour identifier finement |
| Bonus | Wokwi, flash WebSerial, prix fournisseurs en direct, export KiCad (tous retenus) |
| LLM | Local d'abord (Ollama). Secours : Gemini (offre gratuite) puis Claude (payant à l'usage, optionnel) |
| Matériel | Mac mini M4 16 Go, PC bureau Win11 (128 Go RAM, 8 Go VRAM), PC école Win11 (12 Go RAM, 6–8 Go VRAM) : **profils adaptatifs** |
| Révisions | App locale Docker + site statique GitHub Pages ; modules : prépa E1–E5, flashcards, podcast, cartes mentales |

---

## 1. Organisation du dépôt (monorepo, workspace uv)

Étape 0 : `git merge origin/main`, puis on range les fichiers avec `git mv`.
```
PCO/
├── cours/                    # supports de cours (déplacés depuis la racine, inchangés)
├── referentiel/              # PDF du référentiel + referentiel.yaml (C1–C21 structuré : critères, livrables)
├── packages/
│   └── llm_gateway/          # client IA commun (LiteLLM/Ollama/Gemini/Claude), profils matériel, FakeProvider
├── microforge/               # PROJET DE FIN D'ÉTUDES (détail §3–§5)
├── revision/                 # Révisions DevIA (détail §6)
├── .github/
│   ├── workflows/            # ci, data-tests, model-cd, cd, docs, pages, veille
│   ├── ISSUE_TEMPLATE/       # user story, bug, incident (E5)
│   └── dependabot.yml
├── pyproject.toml            # [tool.uv.workspace], ruff, pytest, coverage
├── .pre-commit-config.yaml   # ruff, gitleaks, end-of-file, check-yaml
└── README.md                 # vue d'ensemble + démarrage rapide par machine
```
Chaque projet pourra être extrait plus tard dans son propre dépôt avec `git subtree split` si le jury
préfère un dépôt par projet.

---

## 2. Boîte à outils complète

Le cours d'origine est indiqué entre parenthèses ; ✚ signale un outil ajouté, avec sa justification.

### 2.1 Environnement, qualité, documentation
| Outil | Rôle | Compétences |
|---|---|---|
| **uv** (MLOPS 0) | workspace, lockfile `uv.lock`, groupes `dev/data/ia/docs`, scripts `[project.scripts]` | C15, C17 |
| **ruff** (MLOPS 0) | lint + format ; pre-commit | C17, C18 |
| **pytest, pytest-cov, pytest-mock** (OPCO Pytest) | tests unitaires et d'intégration, couverture ≥ 80 % | C9, C10, C12, C17, C18 |
| ✚ **hypothesis** | tests par propriétés de l'allocateur de broches (aucune broche attribuée deux fois…) | C12, C17 |
| ✚ **respx / pytest-httpx** | rejouer les réponses HTTP des API fournisseurs (tests hors ligne) | C1, C12 |
| **loguru** (OPCO Loguru) | logs JSON structurés, rotation/rétention, `request_id` corrélé | C20, C21 |
| **pydantic-settings + python-dotenv** | config `.env` / `.env.example` (aucun secret dans Git) | C8, C17 |
| **Sphinx + Furo + MyST + autodoc** (IA DOCS Sphinx, dépôt `Sphinx-Furo`) | doc technique et dossiers E1–E5 en HTML accessible, publiée sur Pages | tous |
| **Git + GitHub** (WORKFLOW I) | branches feature/PR, conventional commits, protection de `main` | C3, C9… |
| **GitHub Projects** | backlog Scrum, tableau kanban, itérations, graphique burndown | C16 |
| ✚ **gitleaks** (MLOPS 1) | détection de secrets en pre-commit et en CI | C17, C18 |
| ✚ **pip-audit / npm audit / Dependabot** | vulnérabilités des dépendances | C17, C18 |

### 2.2 Données (E1)
| Outil | Rôle |
|---|---|
| **httpx + tenacity** | appels REST (OAuth2, retries exponentiels, respect des 429) |
| **BeautifulSoup4 + lxml** | parsing du HTML scrapé |
| ✚ **Playwright** (équivalent du Selenium vu dans HorRAGor) | pages rendues en JavaScript |
| `urllib.robotparser` | respect de `robots.txt` |
| **Polars** (HorRAGor) | nettoyage et agrégation rapides ; **pandera** pour les schémas de validation |
| **PySpark / Spark SQL** (HorRAGor) | traitement big data du catalogue LCSC |
| ✚ **BigQuery (option)** | SQL sur le dataset public GitHub (fichiers `.ino`) |
| **rapidfuzz** (Levenshtein, HorRAGor) | dédoublonnage approximatif des références |
| **SQLAlchemy 2 / SQLModel + Alembic** (SQLAlchemy, SQLModel) | ORM, migrations versionnées |
| **PostgreSQL 17 + pgvector** | base applicative et vecteurs (datasheets), donc pas de service vectoriel en plus (sobriété) |
| **MinIO** (MLOPS 2) | stockage objet : dumps bruts, HTML, photos, artefacts MLflow, remote DVC |
| **Prefect 3** (MLOPS 3) | orchestration des flows (collecte, agrégation, purge RGPD, veille), planification cron |
| ✚ **Mocodo / Looping** | MCD/MLD Merise à partir d'un texte, avec export d'images |

### 2.3 Applicatif
| Outil | Rôle |
|---|---|
| **FastAPI + Pydantic v2 + uvicorn** | `api_data` et `api_ia` (deux API séparées, comme l'exige le formateur) |
| **PyJWT** (RS256), **pwdlib[argon2]**, **cryptography (Fernet)**, **slowapi**, CORS (Sécuriser API FastAPI) | JWT access + refresh avec rotation et révocation, hachage, chiffrement des données personnelles, limitation de débit |
| **Celery + Redis + Flower** (MLOPS 4) | tâches longues : génération, compilation, inférence par lots |
| **Streamlit** (DEV IA Streamlit) | preuve de concept multipage, avec `st.camera_input` |
| ✚ **React 19 + Vite + TypeScript + Tailwind + vite-plugin-pwa** | PWA mobile installable, caméra, hors ligne partiel |
| ✚ **TanStack Query, React Router, react-hook-form + zod** | appels API, navigation, formulaires validés |
| ✚ **Vitest + Testing Library, Playwright, @axe-core/playwright, Lighthouse CI, EcoIndex** | tests front, tests de bout en bout (E2E), accessibilité automatisée, éco-conception |
| ✚ **arduino-cli / PlatformIO** | compilation de vérification du firmware généré |
| ✚ **esptool-js** | flash de l'ESP32 depuis le navigateur (WebSerial) |
| ✚ **avr8js + @wokwi/elements** | simulation Arduino AVR dans le navigateur et rendu breadboard ; `diagram.json` importable sur wokwi.com |
| ✚ **schemdraw** | schéma électrique SVG |
| ✚ **SKiDL** | netlist KiCad |
| **Traefik** (tuto-traefik) | reverse proxy, TLS, routage par labels, authentification des interfaces d'administration |

### 2.4 IA et MLOps
| Outil | Rôle |
|---|---|
| **Ollama** (IA Agentic) | modèles locaux : texte/code (famille Qwen3), vision (Qwen3-VL / Gemma), embeddings (bge-m3 ou nomic-embed-text) |
| ✚ **LiteLLM Proxy** | passerelle unique compatible OpenAI : clés virtuelles par service, quotas, **fallbacks** Ollama → Gemini → Claude, métriques. ⚠️ **image Docker épinglée par digest** : les versions PyPI 1.82.7/1.82.8 ont été compromises en mars 2026 |
| **LangChain + LangGraph** (IA Agentic) | pipeline de génération de projet (graphe d'états), RAG sur les datasheets |
| ✚ **Langfuse** (cité dans IA Agentic) | traces LLM, versions de prompts, coût et latence |
| **Ultralytics YOLO (YOLO11/YOLO26)** (Idées de projets FH) | détecteur de composants. Licence AGPL-3.0, compatible car le dépôt est public |
| ✚ **RF-DETR** (Apache 2.0, tailles N/S/M/L) | alternative comparée dans le benchmark C7 |
| ✚ **Label Studio** (ou Roboflow, plan gratuit) | annotation des photos |
| **MLflow** (MLOPS 2) | tracking + registre avec alias `@staging` / `@production`, artefacts dans MinIO, backend Postgres |
| ✚ **DVC** | versionnement du dataset d'images (remote MinIO S3), exigé par C12 (« si possible des données ») |
| ✚ **Evidently** | rapports de dérive (données, prédictions) pour C11 |
| ✚ **CodeCarbon** | mesure énergie/CO₂ des inférences et entraînements (critère éco-responsabilité C7/C15) |
| ✚ **Piper TTS** | voix locales pour le podcast des révisions |

### 2.5 Infrastructure, CI/CD, observabilité
| Outil | Rôle |
|---|---|
| **Docker + docker compose** (MLOPS 0/1) | profils `core`, `ai`, `mlops`, `monitoring`, `veille`. Images officielles ; éviter Bitnami, dont le catalogue public est restreint depuis 2025 |
| **GitHub Actions** (MLOPS 0, cicd-intro) | CI, CD application, CD modèle, docs, Pages. **Actions épinglées par SHA de commit** (veille sécurité : compromission Trivy/TeamPCP en 2026) |
| ✚ **Runner GitHub auto-hébergé** (PC du bureau, GPU 8 Go) | entraînements YOLO déclenchés par la CI (label `gpu`) |
| **GHCR + docker buildx** | images multi-architecture amd64/arm64 (Windows et Mac M4) |
| **Prometheus + prometheus-fastapi-instrumentator** (MLOPS 3 Monitoring) | métriques API, Celery, LLM, modèle |
| **Grafana** (provisioning + alerting) | dashboards et alertes vers Discord et e-mail |
| **Loki + Grafana Alloy** (Tuto Loki) | logs centralisés. **Alloy remplace Promtail, en fin de vie depuis mars 2026** |
| **Uptime Kuma** (MLOPS 3) | disponibilité des services, webhook Discord |
| Kubernetes + KEDA (Projet 5.0) | **bonus optionnel** : manifests `k8s/` (core, mlops, scaling, monitoring) |

### 2.6 Profils matériel (`packages/llm_gateway/profiles.yaml`, forçables avec `MF_PROFILE`)
| Profil | Détection | LLM texte/code | Vision | YOLO (entraînement) | Remarque |
|---|---|---|---|---|---|
| `mac-m4-16` | macOS arm64, 16 Go | 8B | VLM 4B–8B | `device=mps`, taille n/s | **Ollama natif** (Metal), car Docker Mac n'a pas accès au GPU ; les conteneurs passent par `host.docker.internal:11434` |
| `win-8gb` | CUDA ≥ 8 Go | 8B (14B en déchargement partiel grâce aux 128 Go de RAM) | VLM 8B | `cuda`, taille s/m, batch 16 | runner CI GPU |
| `win-6gb` | CUDA 6–8 Go, RAM ≤ 16 Go | 4B | VLM 2B–4B | `cuda`, taille n | PC école |
| `cpu` | aucun GPU | 4B | → Gemini | Colab/Kaggle | secours |

Les noms exacts des modèles se règlent dans la config (`ollama list`) : aucun nom codé en dur.

---

## 3. MicroForge — description fonctionnelle

### Parcours utilisateurs
1. **Inventaire photo** :
   - photo du bac ou du tiroir (mobile), compressée côté client, métadonnées EXIF/GPS supprimées ;
   - YOLO détecte (boîtes + classes), le VLM identifie chaque zone (marquages, modèle exact : « DHT22 », « ESP32-WROOM-32 DevKit V1 ») ;
   - l'utilisateur valide ou corrige, de façon accessible (liste texte éditable au clavier) ;
   - l'inventaire est mis à jour (quantité, emplacement, état). Les corrections alimentent la boucle de feedback (C11).
2. **Que puis-je construire ?** :
   - ~30 modèles de projets (station météo, arrosage, radar de recul, serrure RFID, horloge NTP OLED, robot évitement, lampe NeoPixel, alarme PIR…) ;
   - plus des idées « minées » à partir des sketches réels (big data, §5 C1) ;
   - plus des idées libres du LLM, contraintes à l'inventaire ;
   - chaque idée est validée par l'allocateur, et le classement tient compte de la part de l'inventaire utilisée, de la difficulté et des pièces manquantes.
3. **Générer le projet** (graphe LangGraph) :
   1. spécification → BOM ;
   2. **allocateur de broches déterministe** → **ERC** (contrôle électrique) → netlist ;
   3. firmware (Arduino C++ / PlatformIO, MicroPython en option) généré à partir de la spec structurée, puis `arduino-cli compile` ;
   4. **sorties** : tableau de câblage, schéma SVG, vue breadboard, **guide de soudure pas-à-pas** (outillage, ordre : alimentation → bus → capteurs → actionneurs, points de contrôle au multimètre), `diagram.json` Wokwi + simulation avr8js, netlist KiCad, zip du projet, flash WebSerial.
4. **« Je veux construire X »** :
   - même pipeline à partir d'un objectif en texte libre ;
   - **liste d'achat = BOM − inventaire** ;
   - offres des fournisseurs (prix en EUR, stock, lien), regroupées pour minimiser le nombre de boutiques ;
   - export CSV/PDF.
5. **Compte et RGPD** : inscription, export de mes données, suppression du compte, consentement optionnel à l'utilisation des photos pour l'entraînement.

### Garde-fous techniques (fiabilité)
- Le **LLM n'attribue jamais une broche** : il produit une spec, et le code déterministe câble.
- **Cartes de capacités des cartes** :
  - ESP32 : broches de démarrage 0/2/12/15 évitées, 6–11 réservées à la flash, 34–39 en entrée seule, **ADC2 interdit si le Wi-Fi est utilisé**, I2C par défaut 21/22 ;
  - Uno/Nano : A4/A5 pour l'I2C, PWM sur 3/5/6/9/10/11 ;
  - Pico : I2C/SPI sur n'importe quel GPIO compatible.
- **ERC** :
  - 5 V vers un GPIO 3,3 V → ajout d'un pont diviseur ou d'un level shifter ;
  - budget de courant (servo/relais → alimentation externe + diode de roue libre) ;
  - adresses I2C en conflit ;
  - résistance de pull-up manquante, LED sans résistance.

---

## 4. MicroForge — architecture technique

```
microforge/
├── data_pipeline/            # E1 — flows Prefect
│   ├── extract/{rest_digikey,rest_mouser,rest_github,rest_fx,file_arduino_index,file_fritzing,
│   │            file_boards,file_datasheets,scrape_shop,scrape_projects,db_jlcparts,bigdata_spark,bigdata_bigquery}.py
│   ├── aggregate/            # règles C3 + schémas pandera
│   ├── load/                 # import Postgres (C4) + purge RGPD
│   ├── sql/                  # requêtes .sql documentées (C2)
│   └── flows.py              # point d'entrée : collecte → agrégation → import
├── core/                     # logique métier pure (testée à fond)
│   ├── catalog/              # ~80 pièces YAML (broches, tensions, interfaces, libs, wokwi_type, kicad_symbol)
│   ├── boards/               # cartes de capacités ESP32/ESP32-S3/C3, Uno, Nano, Mega, Pico
│   ├── allocator.py  erc.py  netlist.py  bom.py  shopping.py  templates/ (modèles de projets)
│   └── outputs/{wiring_table,schematic_svg,wokwi,soldering_guide,kicad_skidl,zip}.py
├── api_data/                 # FastAPI : auth, users, catalogue, inventaire, projets, offres, listes d'achat
├── api_ia/                   # FastAPI : vision, suggestions, génération, feedback, modèle courant
├── worker/                   # Celery : génération, compilation, inférence par lots
├── ml/                       # YOLO : dataset DVC, train.py (device auto), evaluate.py, register.py, notebook Colab
├── monitoring/               # Prometheus rules, Grafana dashboards (JSON provisionnés), Alloy, Uptime Kuma
├── app_streamlit/            # preuve de concept
├── app_pwa/                  # React PWA (phase 2)
├── benchmark/                # C7 : protocole + scripts de mesure + résultats
├── veille/                   # C6 : OPML, grille de fiabilité, synthèses
├── infra/                    # compose.*.yml, traefik, litellm config, k8s/ (bonus)
└── docs/                     # Sphinx : dossiers E1…E5, specs, MCD, RGPD, user stories, runbooks
```

**Flux** :
- photo → `api_ia` (JWT vérifié avec la clé publique RS256 de `api_data`) → YOLO (modèle MLflow `@production`) → LiteLLM → Ollama/Gemini → résultats → `api_data` (inventaire) ;
- génération → tâche Celery → `core` → sorties dans MinIO → URL signée.

**Ports internes uniquement**, publiés par Traefik : `api.microforge.localhost`, `ia.…`, `app.…`,
`grafana.…`, `mlflow.…` (auth).

---

## 5. Référentiel — ce que MicroForge produit pour chaque compétence

> Chaque épreuve correspond à un **rapport professionnel individuel**. Il est rédigé dans `microforge/docs/E<n>/`, à partir de gabarits que je crée dès cette session, avec une check-list des critères.

### E1 — Bloc 1 : collecte, stockage et mise à disposition des données (C1–C5)
Service numérique : **« Base de connaissances composants & prix »**, qui alimente MicroForge.

#### C1 — Extraction automatisée depuis 5 types de sources
Le critère exige un « mix entre au moins : service web REST, fichier, scraping, base de données, système big data ».

| Type | Cible | Données récupérées | Technique | Contraintes identifiées (à documenter) |
|---|---|---|---|---|
| **1. Service web REST** | **DigiKey Product Information API v4** (KeywordSearch, ProductDetails) | MPN, fabricant, description, paramètres (tension, courant, interface), URL datasheet, prix par paliers, stock | httpx + OAuth2 client credentials, pagination, cache local, tenacity sur 429 | compte développeur gratuit, quotas par minute et par jour (à relever sur le portail), CGU d'usage des données |
| | **Mouser Search API** (complément) | prix EUR, stock, lien produit | clé d'API, 1 requête/s côté client | quota exact non publié : à mesurer et documenter |
| | **GitHub REST API** | dépôts de bibliothèques Arduino : étoiles, dernier commit, licence → score de qualité | jeton personnel, `search/repositories`, en-têtes de limite de débit | 5 000 requêtes/h authentifié |
| | **Frankfurter** (taux BCE, sans clé) | taux USD/CNY → EUR datés | GET simple | normalisation monétaire (C3) |
| **2. Fichiers de données** | **`library_index.json`** Arduino (downloads.arduino.cc) | ~7 000+ bibliothèques : versions, architectures, `providesIncludes` → lien composant ↔ bibliothèque ↔ `#include` | téléchargement en flux + parsing JSON (Polars) | gros fichier, versionner la date de snapshot |
| | **Pièces Fritzing** (`.fzp` XML, licence CC-BY-SA) | brochage des modules (nom et description des connecteurs, famille, propriétés) | `lxml`, XPath | licence à citer, pièces hétérogènes |
| | **`boards.txt`** des cœurs ESP32/AVR + `pio boards --json-output` | specs des cartes (MCU, flash, RAM, fréquence) | parsing clé=valeur et JSON | — |
| | **Datasheets PDF** (URL issues de l'API) | texte des pinouts et valeurs maximales absolues → **RAG** | pypdf/pdfplumber, découpage en chunks, embeddings | protection SSRF : liste blanche de domaines, taille maximale |
| **3. Scraping** | **Boutique française** (candidats : Gotronic, Kubii ou Lextronic ; **choix final après lecture des CGU et de `robots.txt`**) | prix TTC EUR, disponibilité, référence boutique | **téléchargement et archivage du HTML** (MinIO) puis parsing BeautifulSoup ; Playwright si JS ; délai de 3 s, User-Agent identifié | robots.txt, CGU, données publiques uniquement, aucune donnée personnelle |
| | **Pages de tutoriels de projets** (ex. Random Nerd Tutorials, sous réserve des CGU) | **métadonnées** seulement : titre, carte, liste « Parts Required », lien → dataset d'idées de projets | idem | droit d'auteur : pas de recopie du contenu, lien vers la source |
| **4. Base de données** | **jlcparts `cache.sqlite3`** (catalogue JLCPCB/LCSC, ~11 Go ; version allégée jlcsearch < 2 Go) | composants, catégories, fabricants, boîtiers, stock, prix (JSON), attributs | connexion SQLAlchemy (SQLite), requêtes SQL avec jointures (C2) | volumétrie : indexer, filtrer tôt ; snapshot daté (stock non temps réel) |
| **5. Système big data** | **Apache Spark** (image officielle `apache/spark`, mode local ou standalone) sur le **catalogue LCSC complet** exporté en Parquet | statistiques prix/catégories, sélection « maker-friendly » (traversant ou module, stock > seuil) | **Spark SQL** (C2) : partitionnement par catégorie, pushdown Parquet, broadcast join | mémoire : plafonner `spark.driver.memory` selon le profil |
| | **Option : BigQuery**, dataset public `github_repos.sample_contents` | co-occurrences de `#include` dans les fichiers `.ino` → combinaisons réelles de composants → idées de projets | SQL BigQuery, **dry-run obligatoire** pour estimer les octets | offre gratuite de 1 To/mois : n'utiliser que les tables `sample_*` |

**Structure imposée de chaque script** (critère C1) :
1. point de lancement (CLI Typer + flow Prefect) ;
2. initialisation (config, clients, connexions) ;
3. règles de traitement ;
4. gestion des erreurs (exceptions typées, retries, logs loguru) ;
5. fin et sauvegarde (Parquet brut daté dans MinIO + manifeste JSON).

#### C2 — Requêtes SQL documentées (`data_pipeline/sql/*.sql` + `docs/E1/requetes.md`)
- **SQLite jlcparts** :
  - jointure `components ⋈ categories ⋈ manufacturers` ;
  - filtre des sous-catégories utiles (MCU, capteurs, afficheurs, drivers moteur, passifs traversants) avec `stock > 100` ;
  - fonction fenêtre `ROW_NUMBER() OVER (PARTITION BY mfr ORDER BY stock DESC)` pour garder la meilleure offre ;
  - `EXPLAIN QUERY PLAN` avant et après la création d'index.
- **Spark SQL** :
  - médiane des prix par catégorie (`percentile_approx`) ;
  - top fabricants ;
  - répartition des boîtiers traversant/CMS ;
  - optimisations documentées : partitions, projection minimale, cache, broadcast.
- **BigQuery** : `REGEXP_EXTRACT_ALL(content, r'#include\s*[<"]([^>"]+)')`, puis paires co-occurrentes avec leur support.
- La documentation explique, pour chaque requête : l'objectif, les sélections, filtres, conditions et jointures, et les optimisations appliquées.

#### C3 — Agrégation et nettoyage (`data_pipeline/aggregate/`)
- **Clé d'unification** : (fabricant normalisé, MPN normalisé). Les modules (« DHT22 module ») passent par une table d'alias. rapidfuzz ≥ 90 sert au rapprochement ; les cas douteux vont dans une file de revue.
- **Entrées corrompues**, détectées puis supprimées ou mises en quarantaine :
  - MPN et nom absents ;
  - prix ≤ 0 ou aberrant (règle IQR, comme dans le cours Pandas) ;
  - stock négatif ;
  - doublons exacts ;
  - datasheet introuvable (signalée, pas supprimée).
- **Homogénéisation** :
  - unités SI (« 3V3 », « 3.3V », « 3,3 V » → `3.3` en volts ; mA → A) ;
  - devises en EUR au taux BCE de la date de collecte ;
  - dates ISO 8601, UTF-8 ;
  - boîtiers canoniques (DIP-8, SOT-23…) ;
  - vocabulaire contrôlé des interfaces (I2C, SPI, UART, 1-Wire, PWM, ADC, GPIO).
- **Sorties** : `components_clean.parquet` + **rapport de rejets** (nombre par règle). Schémas pandera ; tests pytest.

#### C4 — Base de données conforme au RGPD
- **SGBD** : PostgreSQL 17 + pgvector. Le choix est justifié face à SQLite (concurrence, rôles) et MongoDB (données très relationnelles).
- **MCD Merise** (Mocodo/Looping) :

  | Groupe | Entités et associations |
  |---|---|
  | Utilisateurs | UTILISATEUR, RÔLE |
  | Catalogue | COMPOSANT, CATÉGORIE, FABRICANT, BROCHE, INTERFACE, CARTE (spécialisation de COMPOSANT), BIBLIOTHÈQUE, *UTILISE* (composant–bibliothèque) |
  | Achats | FOURNISSEUR, OFFRE (prix, stock, date) |
  | Inventaire | ARTICLE_INVENTAIRE (utilisateur × composant, quantité, emplacement), PHOTO, DÉTECTION (boîte, classe, confiance, corrigée) |
  | Projets | MODÈLE_PROJET, PROJET, LIGNE_BOM, CONNEXION (netlist), LISTE_ACHAT |
  | RAG | DOCUMENT_CHUNK (vecteur) |
  | Feedback | FEEDBACK |

  MCD → MLD → MPD (DDL), avec migrations Alembic.
- **Procédure d'installation** reproductible (compose + `alembic upgrade head` + script d'import), testée sur Mac et Windows.
- **RGPD** :
  - **registre des traitements** : comptes, photos, logs, feedback, chacun avec finalité, base légale, catégories de données, durée de conservation, destinataires et mesures de sécurité ;
  - **données minimisées** : e-mail chiffré (Fernet) + index haché pour la recherche, pseudo, ville facultative ; mots de passe hachés en argon2 ;
  - **procédures de tri** : flow Prefect `purge_rgpd` hebdomadaire. Il supprime les photos 30 jours après traitement (sauf consentement pour l'entraînement, et alors seulement les découpes anonymes), les comptes inactifs depuis 24 mois (après e-mail de préavis) et les logs de plus de 6 mois. Il trace ses exécutions.
- **Script d'import** documenté (dépendances, commandes), versionné à la racine du même dépôt.

#### C5 — API REST de mise à disposition (`api_data`)
- **Points de terminaison** :
  - auth : `POST /v1/auth/register|token|refresh|logout` ;
  - utilisateur : `GET/DELETE /v1/users/me`, `GET /v1/users/me/export` (portabilité RGPD) ;
  - catalogue : `GET /v1/components` (recherche, filtres, pagination plafonnée), `/v1/components/{id}`, `/{id}/offers`, `/{id}/pins`, `/v1/boards`, `/v1/libraries` ;
  - inventaire : `CRUD /v1/inventory`, `POST /v1/inventory/bulk` ;
  - projets : `CRUD /v1/projects`, `/v1/shopping-lists` ;
  - admin : `GET /v1/admin/ingestion-runs`.
- **Sécurité** : JWT RS256 (access 15 min, refresh 7 j avec rotation et détection de réutilisation), rôles `user`/`admin`, et le **Top 10 OWASP API 2023** traité point par point :

  | Risque OWASP | Mesure |
  |---|---|
  | BOLA (autorisation au niveau objet) | vérification du propriétaire de chaque inventaire et projet |
  | Authentification | limitation de débit sur `/token` |
  | BOPLA (propriétés exposées) | `response_model` stricts |
  | Consommation de ressources | pagination et tailles maximales |
  | BFLA (autorisation des fonctions) | rôle admin |
  | SSRF | liste blanche des URL de datasheets |
  | Mauvaise configuration | CORS restreint, en-têtes de sécurité |
  | Inventaire des API | versionnement `/v1` |
  | Consommation d'API tierces | validation des réponses fournisseurs |
- **Documentation** : OpenAPI générée + page Sphinx (règles d'authentification, exemples) + doc d'**accès direct à la base** (rôle PostgreSQL `analyst` en lecture seule, chaîne de connexion type).

### E2 — Bloc 2 : veille, benchmark et paramétrage d'un service d'IA (C6–C8)

#### C6 — Veille technique et réglementaire (démarre dès la 1re semaine : il faut des traces régulières)
- **Thématiques**, liées au projet comme l'exige le critère :
  - **T1 – Technique** : détection d'objets légère et VLM open-source exécutables en local (YOLO, RF-DETR, Qwen-VL, Gemma), outillage LLM local (Ollama, LiteLLM), écosystème ESP32/Arduino.
  - **T2 – Réglementaire et sécurité** :
    - **AI Act** (Règlement (UE) 2024/1689 et omnibus numérique IA de 2026 : obligations « haut risque » reportées, transparence de l'**article 50** applicable depuis le 2 août 2026 ; MicroForge relève du risque minimal mais doit **signaler les contenus générés par l'IA**) ;
    - **RGPD / recommandations IA de la CNIL** ;
    - **accessibilité** (RGAA 4.1, European Accessibility Act) ;
    - **éco-conception** (RGESN) ;
    - **sécurité de la chaîne d'approvisionnement logicielle** (cas d'étude 2026 : compromission de Trivy et de LiteLLM sur PyPI).
- **Sources**, chacune notée avec la grille de fiabilité ci-dessous :

  | Catégorie | Exemples |
  |---|---|
  | Officielles | EUR-Lex, CNIL (RSS), Commission/AI Office, CERT-FR/ANSSI (avis RSS), numerique.gouv.fr (RGAA, RGESN), W3C WAI |
  | Primaires techniques | flux RSS des *releases* GitHub (`ollama/ollama`, `ultralytics/ultralytics`, `roboflow/rf-detr`, `BerriAI/litellm`, `espressif/arduino-esp32`, `langchain-ai/langgraph`), blog et *daily papers* Hugging Face, arXiv cs.CV filtré par mots-clés, blogs Espressif et Arduino, GitHub Security Advisories / OSV |
  | Analyse | blog de Simon Willison, The Batch (DeepLearning.AI), Hackaday, Korben et LinuxFr (FR) |
  | Signaux faibles | r/LocalLLaMA, Hacker News : jamais cités seuls, toujours recoupés |
- **Grille de fiabilité** (/7, une source est retenue à partir de 5) :
  - auteur identifié ;
  - compétence ou notoriété sans conflit d'intérêts ;
  - date récente ;
  - sources citées et niveau de langue correct ;
  - contenu structuré ;
  - accessibilité du site ;
  - recoupement possible.
- **Outils** :
  - agrégation : **FreshRSS auto-hébergé** (Docker, gratuit, export OPML, filtres et étiquettes, API) ;
  - automatisation : flow Prefect `veille_weekly`. Il récupère les nouveaux articles via l'API FreshRSS, fait rédiger un **brouillon de synthèse par le LLM local**, que Gaël relit (validation humaine obligatoire), puis le publie ;
  - partage : page HTML accessible sur le site de documentation, e-mail ou Discord à la promo et au formateur.
- **Planning** : **lundi 9h–10h** (le critère impose au minimum 1 h par semaine) + 15 min de tri le vendredi. Un **journal de veille** (date, durée, sources lues, décisions) sert de preuve.
- **Format accessible** (recommandations Valentin Haüy / AcceDe) :
  - titres hiérarchisés, langage clair ;
  - liens explicites, alternatives textuelles, contraste AA ;
  - aucune information portée uniquement par la couleur ;
  - PDF balisé s'il y a un PDF.
- **Livrables `docs/E2/veille/`** : plan de veille, sources + grilles, OPML, ≥ 8 synthèses hebdomadaires, synthèse finale avec recommandations pour le projet.

#### C7 — Benchmark des services d'IA (`microforge/benchmark/`)
- **Besoin reformulé** :
  - F1 détecter et localiser des composants multiples sur une photo ;
  - F2 identifier finement (référence, marquages) ;
  - F3 générer du firmware ;
  - F4 raisonner sur le câblage (assisté par règles) ;
  - F5 embeddings pour le RAG des datasheets.
- **Contraintes** :
  - budget ~0 € ;
  - local d'abord (photos personnelles, RGPD) ;
  - matériel : 16 Go unifiés / 8 Go / 6 Go de VRAM ;
  - latence < 5 s par photo, hors ligne possible ;
  - licence compatible ;
  - sobriété énergétique.
- **Services étudiés** :

  | Fonction | Services |
  |---|---|
  | Détection | YOLO11/YOLO26 (AGPL-3.0), RF-DETR (Apache 2.0), Roboflow Hosted Inference, Azure AI Custom Vision, Google Vertex AutoML, AWS Rekognition Custom Labels |
  | VLM | Qwen3-VL 2B/4B/8B (Ollama), Gemma 3/4, Moondream, Gemini Flash (offre gratuite aux quotas changeants), Claude (payant), GPT-4o/5 (payant), Mistral Small/Pixtral |
  | Code | Qwen3 / Qwen-Coder local, Gemini, Claude |

  Une liste des **services non étudiés, avec la raison**, complète le tableau (critère explicite).
- **Protocole mesuré** : même jeu de 50 photos de test. Pour chaque service :
  - mAP50 / précision top-1 ;
  - latence p50/p95 ;
  - énergie mesurée avec CodeCarbon ;
  - coût par 1 000 requêtes ;
  - confidentialité (lieu d'hébergement, réutilisation des données) ;
  - licence, prérequis, maturité.
- **Grille** : adéquation de 0 à 3 par fonction F1–F5, avantages et inconvénients, puis conclusions distinguant clairement les services retenus et écartés.

#### C8 — Paramétrage du service retenu : Ollama auto-hébergé + passerelle LiteLLM
- **Environnement** :
  - Windows bureau : Docker Desktop + WSL2 + NVIDIA Container Toolkit ;
  - Mac : Ollama natif ;
  - compose `infra/compose.ai.yml`.
- **Dépendances** :
  - modèles tirés (`ollama pull …` selon le profil) ;
  - `litellm/config.yaml` : liste des modèles, **fallbacks** vers Gemini, timeouts, routage ;
  - image LiteLLM **épinglée par digest**.
- **Accès** :
  - **clés virtuelles par service** (`api_ia`, `revision-api`, `dev`), budgets et limites de débit ;
  - le port Ollama n'est **pas exposé** (réseau interne Docker) ;
  - l'interface d'administration est derrière Traefik (TLS + authentification).
- **Monitoring** :
  - métriques LiteLLM (requêtes, latence, tokens, erreurs, taux de fallback) vers Prometheus et Grafana. Si ces métriques ne sont pas en open-source, un exporteur maison passera par les callbacks ;
  - traces Langfuse ;
  - sonde Uptime Kuma sur `/health`.
- **Documentation** : gestion des accès, installation, script de test fumée, dépendances et interconnexions, données manipulées (prompts et photos non conservées), format accessible.

### E3 — Bloc 2 : intégrer un modèle d'IA avec une approche MLOps (C9–C13)
Le modèle « fourni » est le **détecteur YOLO de composants**, entraîné en S4 puis mis en service.

#### Dataset (`ml/`)
- **Sources** :
  - Roboflow Universe (Arduino, ESP32, breadboard, composants ; licences CC BY 4.0 à vérifier une à une) ;
  - dataset Mendeley « IoT kits » (DOI 10.17632/x5thzmkxhy.1) ;
  - **photos personnelles** (objectif 600–1 000 images, ~30–40 classes), annotées dans Label Studio.
- **Augmentations** : albumentations (luminosité, flou, rotation).
- Versionnement **DVC** (remote MinIO) ; découpage train/val/test sans fuite (hash perceptuel).

#### C9 — API d'exposition du modèle (`api_ia`)
- **Points de terminaison** :
  - `POST /v1/vision/detect` (multipart ≤ 8 Mo, jpeg/png/webp vérifiés avec Pillow, EXIF supprimé, redimensionnement) → `[{class, bbox, confidence}]` ;
  - `POST /v1/vision/identify` (découpe → VLM) ;
  - `POST /v1/builds/suggest|generate|from-goal` (génération asynchrone → `GET /v1/tasks/{id}`) ;
  - `POST /v1/feedback` ;
  - `GET /v1/models/current` ;
  - `/health`, `/metrics`.
- **Sécurité** : JWT RS256 vérifié avec la clé publique, scopes `vision:use` / `admin`, quotas par utilisateur (429), timeouts, OWASP.
- **Tests d'intégration** : TestClient + images de référence + `FakeProvider`, tous les points de terminaison couverts. Doc OpenAPI + Sphinx.

#### C10 — Intégration dans l'application
- Streamlit puis PWA :
  - login, **renouvellement automatique du token** (intercepteur) ;
  - capture caméra, boîtes dessinées sur canvas **plus** une liste texte accessible ;
  - états de chargement et d'erreur.
- **Tests d'intégration** : pytest pour Streamlit (AppTest), Vitest + MSW et Playwright pour la PWA, axe pour l'accessibilité.

#### C11 — Monitoring du modèle
| Métrique | Collecte | Seuil / déclencheur |
|---|---|---|
| Taux de corrections utilisateur (détections modifiées ou supprimées) | table FEEDBACK → job Prefect quotidien → métrique | > 25 % sur 7 jours → alerte + **déclencheur de réentraînement** (`repository_dispatch`) |
| Confiance moyenne et distribution | histogramme Prometheus dans `api_ia` | moyenne < 0,5 sur 24 h → alerte |
| Dérive des classes et des images (PSI, Evidently) | rapport Evidently quotidien (HTML archivé + métriques) | PSI > 0,2 → alerte |
| mAP sur le lot de feedback étiqueté | évaluation hebdomadaire | baisse > 5 points → réentraînement |
| Latence p95, erreurs, mémoire GPU/CPU | instrumentator + cAdvisor | p95 > 2 s → avertissement |

- **Restitution** : dashboard Grafana « Modèle », alertes Discord et e-mail. Accessibilité : palettes daltonien-compatibles, valeurs affichées en texte.
- **Test en bac à sable** : `compose.monitoring-test.yml` + générateur de trafic qui **injecte volontairement une dérive** pour prouver que l'alerte se déclenche.
- Doc technique (installation, maintenance) + doc utilisateur.

#### C12 — Tests automatisés du modèle (`ml/tests/`)
- **Données** :
  - format des labels YOLO (identifiants de classe valides, boîtes normalisées entre 0 et 1) ;
  - images lisibles, pas de doublons (hash) ;
  - pas de fuite entre train, val et test ;
  - équilibre minimal par classe.
- **Préparation** : formes en sortie du letterbox et des augmentations.
- **Entraînement** : test fumée d'une epoch sur 8 images en CPU (la perte est finie, l'artefact est produit).
- **Évaluation** : métriques calculées ; **porte de non-régression** : mAP50 ≥ mAP de `@production` − 2 points.
- **Inférence** : schéma de sortie, déterminisme sur une image de référence.
- Outils : pytest, fixtures, mocks ; données sous DVC ; doc d'installation et d'exécution, calcul de la couverture.

#### C13 — Chaîne de livraison continue du modèle (`.github/workflows/model-cd.yml`)
- **Déclencheurs** : push sur `ml/**` ou `*.dvc`, `repository_dispatch` (envoyé par le monitoring), `workflow_dispatch`, mensuel (cron).
- **Étapes** :
  1. tests des données ;
  2. **entraînement** sur le runner auto-hébergé `gpu` (secours : Kaggle ou Colab manuel) avec suivi MLflow ;
  3. évaluation : mAP50, mAP50-95, précision et rappel par classe, **matrice de confusion PNG** ;
  4. comparaison avec `@production` ;
  5. enregistrement du candidat avec l'alias `@staging` ;
  6. **ouverture d'une PR « Modèle vX » avec le rapport d'évaluation joint** (critère explicite) ;
  7. la fusion de la PR déclenche la promotion en `@production`, et `api_ia` recharge le modèle à chaud par alias (patron du cours MLOPS 2).
- Doc d'installation, de test et de déclenchement.

### E4 — Bloc 3 : concevoir et développer l'application (C14–C19)

#### C14 — Analyse du besoin
- **Personas** : maker débutant, fablab ou enseignant, étudiant en électronique.
- **~20 user stories**, format « En tant que… je veux… afin de… », avec scénarios Gherkin et **critères d'acceptation incluant des critères RGAA**. Exemples :
  - « Photographier mon stock » : alternatives textuelles des résultats, critère 1.1 ;
  - « Corriger une détection » : utilisable au clavier, critères 7.x et 12.x ;
  - « Générer le guide de soudure » : contraste et structure, critères 3.x et 9.x ;
  - « Liste d'achat » : étiquettes de formulaire, critère 11.1.
- **Modélisation** des données de l'application (MCD) et des parcours (schéma fonctionnel + wireframes **Penpot**, open-source).

#### C15 — Cadre technique
- **Architecture** : micro-services n-tiers, avec diagrammes C4 « contexte » et « conteneurs » (Mermaid) et un **diagramme de flux de données** (critère explicite).
- Choix argumentés des langages et outils (§2).
- **Hébergeur de pré-production éco-responsable** : VPS chez Scaleway, OVHcloud ou Infomaniak, comparés dans le benchmark. Déploiement compose + Traefik + Let's Encrypt.
- **Preuve de concept accessible en pré-production**, puis une **conclusion go/no-go** argumentée.

#### C16 — Pilotage agile
- **Scrum, sprints de 2 semaines** :
  - rôles : Gaël développeur et PO délégué, formateur ou tuteur comme commanditaire ;
  - rituels : planning, journal quotidien asynchrone, revue avec démo, rétrospective.
- **GitHub Projects** : backlog, kanban, itérations, burndown, rendus visibles par le formateur.
- Compte rendu de chaque revue dans `docs/E4/sprints/`, journal des risques et des changements.

#### C17 — Développement
- Environnement : `uv sync`, `npm ci`, compose dev.
- **Interfaces** :
  - intégration des maquettes ;
  - front : validation des formulaires, caméra, canvas, simulation, WebSerial ;
  - **composants métier** : allocateur, ERC, BOM, liste d'achat, générateurs ;
  - **gestion des droits** : rôles et propriété des objets.
- **Sécurité, Top 10 OWASP web** :
  - en-têtes CSP ;
  - sanitisation du Markdown généré (DOMPurify) ;
  - tokens en mémoire et refresh en cookie `HttpOnly SameSite=Strict` ;
  - validation des uploads ;
  - limitation de débit.
- **Éco-conception** (RGESN / EcoIndex) : compression des images côté client, chargement paresseux, cache HTTP, bundle plus petit que 300 ko gzip.
- Tests unitaires et d'intégration couvrant au minimum les composants métier et la gestion des accès. Documentation.

#### C18 — Intégration continue (`ci.yml`)
- Déclencheurs : push et PR.
- **Jobs** :
  - ruff, eslint, tsc ;
  - pytest unitaire et intégration (services Postgres et Redis), **porte de couverture à 80 %** ;
  - Vitest, build front ;
  - gitleaks, pip-audit, npm audit.
- Cache uv/npm, matrice Python 3.12 / 3.13. Doc d'utilisation et de déclenchement.

#### C19 — Livraison continue (`cd.yml`)
- Sur fusion dans `main` ou tag `v*` :
  - build des images buildx multi-architecture → GHCR (+ SBOM) ;
  - **PR de release automatique** (release-please) ;
  - déploiement en pré-production (`docker compose pull && up -d` via SSH) ;
  - tests fumée.
- Procédure de retour arrière documentée.

### E5 — Bloc 3 : maintien en condition opérationnelle (C20–C21)

#### C20 — Monitoring applicatif
| Métrique | Seuil d'alerte | Outil |
|---|---|---|
| Disponibilité des API et du front | panne > 1 min | Uptime Kuma → Discord |
| Latence p95 API | > 2 s pendant 5 min (avertissement), > 5 s (critique) | Prometheus / Grafana |
| Taux d'erreurs 5xx | > 2 % pendant 5 min | Prometheus |
| File Celery | > 50 tâches pendant 10 min | Flower / exporteur |
| Taux d'échec des tâches de génération | > 10 % sur 1 h | Prometheus |
| Taux de fallback LLM (Ollama indisponible) | > 30 % sur 15 min | métriques LiteLLM |
| Échecs de connexion | > 20/min (attaque possible) | Loki (LogQL) |
| Disque, redémarrages de conteneurs | > 85 %, > 3 redémarrages/h | cAdvisor / node-exporter |

- **Journalisation** : loguru JSON, `request_id`, **sans donnée personnelle** (identifiant utilisateur haché), rétention de 6 mois.
- Alertes Grafana vers Discord et e-mail. Doc d'installation et de configuration.

#### C21 — Résolution d'incident
- Gabarit d'issue « Incident » : symptômes, logs, impact, reproduction, cause racine, correctif, prévention.
- **Procédure** :
  1. reproduction en développement ;
  2. débogage documenté dans l'issue ;
  3. **correctif par PR** liée à l'issue ;
  4. post-mortem.
- **Incidents candidats** (ceux qui surviendront réellement seront documentés) :
  - modèle YOLO rechargé à chaque requête → fuite mémoire et OOM ;
  - orientation EXIF qui décale les boîtes ;
  - firmware généré utilisant l'ADC2 avec le Wi-Fi → nouvelle règle ERC ;
  - concurrence lors du rafraîchissement du token dans la PWA.

---

## 6. Révisions DevIA (« NotebookLM amélioré »)

```
revision/
├── ingest/        # convertisseurs → Markdown normalisé + images extraites
├── generate/      # prompts versionnés + schémas Pydantic + vérificateur
├── content/<slug>/  # source.md, fiche.md, quiz.json, flashcards.json, exercices.md, mindmap.md,
│                    # podcast.json (+ .mp3 généré en local), meta.json (hash, compétences, date)
├── boilerplates/  # templates copier
├── api/           # FastAPI locale
├── site/          # Astro + Starlight
├── cli.py         # `revise add|build|serve|podcast`
└── docker-compose.yml
```

### Ingestion (`ingest/`)
| Format | Outil |
|---|---|
| `.md` | extraction des images base64 vers des fichiers (elles font plus de 99 % de certains cours) |
| `.pdf` | pypdf + pdfplumber |
| `.pptx` | python-pptx |
| `.html` | BeautifulSoup + markdownify |
| `.ipynb` | nbformat |
| `.docx` | python-docx |
| URL | trafilatura |
| Dépôt GitHub (ex. dépôts DeVerMyst) | `git clone --depth 1`, README + code |

Option : un VLM local décrit les images des slides pour produire des **alternatives textuelles**.
Découpage par titres, embeddings Ollama (`bge-m3`, multilingue) vers **Chroma** (vu en cours).

### Génération (`generate/`), avec cache sha256 (source + version du prompt)
| Livrable | Schéma |
|---|---|
| Fiche | titre, résumé, objectifs, notions (terme → définition), points clés, extraits de code commentés, pièges fréquents, compétences C1–C21 liées, références aux chunks sources |
| QCM | 10–15 questions : 4 choix, bonne réponse, explication, difficulté, compétence |
| Flashcards | recto / verso / tags (20–30 par cours) |
| Exercices | énoncé, niveau, indices, **corrigé**, et tests pytest quand c'est du code |
| Carte mentale | Markdown markmap (par cours + carte globale de l'année) |
| Podcast | dialogue à deux voix en segments, puis synthèse locale avec **Piper** |
| Oral blanc | questions de jury générées à partir des critères de l'épreuve |

Un **vérificateur** (LLM juge + règles) rejette les éléments qui ne citent aucun chunk source, pour
limiter les hallucinations.

### Site (`site/`, Astro + Starlight, recherche Pagefind intégrée)
- **Accueil** : tableau de bord (progression, cartes à revoir aujourd'hui, prochain oral blanc).
- **Cours** (par thème : Python et Data, SQL et ORM, ML/DL/NLP/Audio, API et sécurité, MLOps, Monitoring, Agentic/RAG) : onglets Fiche | QCM | Flashcards | Exercices | Carte mentale | Podcast | Source.
- **Référentiel** : E1 à E5 → C1 à C21. Pour chaque compétence :
  - critères ;
  - check-list des livrables, cochable et mémorisée localement ;
  - cours et boilerplates liés ;
  - **liens vers les livrables MicroForge correspondants** ;
  - oral blanc.
- **Boilerplates** : catalogue, aperçu de l'arborescence, commande `copier copy`, zip.
- **Glossaire** fusionné (à partir de `glossaire.md` et des notions extraites).
- **Chat et « Ajouter un cours »** : visibles seulement en mode local.

Îlots React :
- QCM ;
- flashcards **FSRS** (`ts-fsrs`, stockage local + export/import JSON) ;
- markmap, Mermaid ;
- lecteur audio ;
- chat en streaming SSE avec citations.

### App locale (`api/`) et publication
- **Points de terminaison** :
  - `POST /sources` (fichier, URL ou dépôt) → tâche de fond : ingestion → génération → reconstruction ;
  - `GET /jobs/{id}` ;
  - `POST /chat` (RAG avec citations) ;
  - `POST /oral-blanc/{epreuve}`.
- **Compose** : `revision-api` + `chroma` + site. Ollama tourne sur l'hôte.
- **Publication** : workflow `pages.yml` (au push qui touche `revision/content` ou `revision/site`) → build statique (`PUBLIC_MODE=static`) → GitHub Pages.
  - Il faut activer Pages dans les réglages du dépôt.
  - Si le dépôt est privé, Pages demande un abonnement payant ; alternatives : Cloudflare Pages ou Netlify.
  - Les fiches sont dérivées des supports du formateur : demander son accord avant de publier publiquement.

### Boilerplates (templates `copier`, rédigés à partir des cours)
| Template | Contenu | Cours source |
|---|---|---|
| `fastapi-jwt-sqlmodel` | access/refresh avec rotation, argon2, slowapi, tests | Sécuriser API FastAPI, SQLModel |
| `two-apis-streamlit` | API données + API IA + application, `.env`, loguru, pytest | Idées de projets FH, Analyse Sentiment |
| `streamlit-multipage` | application multipage | DEV IA Streamlit |
| `mlflow-minio` | registre avec alias, rechargement à chaud | MLOPS 2 |
| `prefect-docker` | flows, déploiement Docker | MLOPS 3 |
| `celery-rabbitmq-flower` | workers, broker, supervision | MLOPS 4 |
| `prometheus-grafana-uptimekuma` | supervision | MLOPS 3 Monitoring |
| `loki-alloy` | logs centralisés | Tuto Loki |
| `k8s-keda` | manifests et autoscaling | Projet 5.0 |
| `rag-langchain-chroma` | RAG | IA Agentic |
| `langgraph-agent-mcp` | agent + MCP | IA Agentic |
| `gha-ci-cd` | ruff, pytest-cov, build et push | MLOPS 0 |
| `sphinx-furo-pages` | doc publiée sur Pages | IA DOCS Sphinx |
| `uv-package` | packaging | MLOPS 0 PACKAGING |

Les dépôts DeVerMyst sont **référencés par lien**, sans copie de code (la plupart n'ont pas de licence).

### Contenu initial
J'écris moi-même le premier jeu (fiches, QCM, flashcards, exercices, cartes mentales, scripts de
podcast) pour les ~32 cours existants, dans les mêmes schémas. Le site est donc utile tout de suite ;
Ollama prendra le relais pour les cours suivants.

---

## 7. Feuille de route (soutenance estimée en mars ou avril 2027)
| Sprint | Dates | Contenu | Épreuves |
|---|---|---|---|
| S0 | 02/11 → 15/11 | Fondations, cœur déterministe, API, preuve de concept Streamlit, site de révision, **lancement de la veille** | — |
| S1 | 16/11 → 29/11 | Collecte des 5 types de sources + spécifications techniques | E1 (C1, C2) |
| S2 | 30/11 → 13/12 | Agrégation, MCD/RGPD, import, `api_data` complète, **rapport E1** | E1 (C3–C5) |
| S3 | 14/12 → 10/01 | Benchmark, LiteLLM + Ollama, **rapport E2** (la veille continue chaque semaine) | E2 |
| S4 | 11/01 → 24/01 | Photos + annotation, DVC, YOLO de référence, MLflow | E3 |
| S5 | 25/01 → 07/02 | `api_ia` vision, monitoring du modèle, CD modèle avec PR de rapport, **rapport E3** | E3 |
| S6 | 08/02 → 21/02 | User stories, maquettes, diagramme de flux, cœur de la PWA, pré-production | E4 |
| S7 | 22/02 → 07/03 | Génération dans la PWA, Wokwi/avr8js, WebSerial, KiCad, CI/CD application | E4 |
| S8 | 08/03 → 21/03 | Monitoring applicatif, alertes, incidents réels documentés, **rapports E4 et E5** | E4, E5 |
| S9 | 22/03 → 04/04 | Audit RGAA, EcoIndex, finitions, répétitions de soutenance (oral blanc du site) | tous |

---

## 8. Ce que je réalise dans cette session (ordre d'exécution)
1. **Fondations** :
   - `git merge origin/main`, rangement dans `cours/` et `referentiel/` ;
   - workspace uv, ruff, pre-commit ;
   - `referentiel.yaml` (C1–C21 avec critères), `ci.yml`.
2. **`packages/llm_gateway`** : client LiteLLM/Ollama/Gemini/Claude, détection des profils, `FakeProvider`, tests.
3. **MicroForge** :
   - `core` complet : catalogue de ~80 pièces, 5 cartes, allocateur, ERC, netlist, BOM, liste d'achat, ~30 modèles de projets, sorties (tableau, SVG, Wokwi, guide de soudure, KiCad/SKiDL, zip) ;
   - `api_data` : auth JWT RS256, users chiffrés, catalogue, inventaire, projets, listes d'achat, OWASP ;
   - `api_ia` : vision avec YOLO si le modèle est présent, sinon VLM ; suggestions, génération, feedback ;
   - `data_pipeline` : les 5 extracteurs avec fixtures enregistrées, agrégation, import, requêtes SQL ;
   - preuve de concept **Streamlit** ;
   - squelette `ml/` (train/evaluate/register, choix automatique du device, notebook Colab) ;
   - `monitoring/` (Prometheus, Grafana, Alloy, Uptime Kuma) et composes `core`, `ai`, `mlops`, `monitoring`, `veille` ;
   - **kit de veille** : FreshRSS, OPML des sources, grille de fiabilité, gabarit de synthèse, flow `veille_weekly` ;
   - `docs/` Sphinx avec les gabarits des dossiers E1 à E5 pré-remplis à partir de ce plan.
4. **Révisions** :
   - ingestion et génération, API locale, CLI `revise` ;
   - site Astro complet (tous les modules) ;
   - boilerplates ;
   - contenu initial écrit pour tous les cours ;
   - workflow Pages.
5. Commits réguliers, `git push -u origin claude/amazing-bohr-o38ndx`. **Pas de PR** sauf si tu la demandes.

**Limites de l'environnement cloud** :
- Ollama, Roboflow et `github.com` (pages web) y sont injoignables : **pas d'entraînement YOLO ni d'appel LLM réel ici**. Tout est testé avec le `FakeProvider` et des fixtures HTTP enregistrées.
- L'entraînement, Ollama et la collecte réelle (clés DigiKey/Mouser) se feront sur tes machines, avec un README pas-à-pas par profil.

## 9. Vérification
- `uv run ruff check . && uv run pytest --cov` → couverture ≥ 80 % sur `core`, `api_data`, `api_ia`, `llm_gateway`, `data_pipeline`, `revision/generate`.
- **Tests clés** :
  - allocateur (hypothesis) : aucune broche réservée ou en double, I2C partagé, ADC1 seulement avec le Wi-Fi ;
  - ERC : 5 V vers GPIO 3,3 V → erreur + correctif proposé ;
  - `diagram.json` conforme au format Wokwi ;
  - liste d'achat = BOM − inventaire ;
  - JWT : login, refresh avec rotation, réutilisation → 401, BOLA → 404/403 ;
  - règles C3 : rapport de rejets attendu sur la fixture ;
  - schémas pandera.
- **Bout en bout** : `docker compose --profile core up` puis scénario scripté :
  1. inscription ;
  2. photo (vision mockée) ;
  3. inventaire ;
  4. suggestions ;
  5. « station météo ESP32 + DHT22 + OLED » → câblage, code, Wokwi, guide de soudure, liste d'achat.

  Captures d'écran Playwright de la preuve de concept Streamlit.
- `arduino-cli compile` du firmware généré pour l'Uno (le cœur AVR est léger) dans la CI.
- **Révisions** :
  - `npm run build` sans erreur, index Pagefind présent ;
  - captures Playwright (cours, QCM, flashcards, carte mentale, référentiel) ;
  - axe sans violation critique ;
  - `revise add` d'un cours d'exemple avec le `FakeProvider` → tous les fichiers produits et valides selon les schémas.

## Sources consultées pour ce plan
- jlcparts / jlcsearch : https://github.com/yaqwsx/jlcparts · https://github.com/yaqwsx/jlcparts-dev · https://github.com/Nicolas-Rozas/jlcsearch
- DigiKey API (limites) : https://developer.digikey.com/documentation
- PlatformIO `pkg search` : https://docs.platformio.org/en/stable/core/userguide/pkg/cmd_search.html
- Compromission LiteLLM (mars 2026) : https://www.netspi.com/blog/executive-blog/ai-ml-pentesting/litellm-supply-chain-compromise/
- Omnibus IA / AI Act : https://www.addleshawgoddard.com/en/insights/insights-briefings/2026/technology/eu-ai-act-ai-omnibus-formally-adopted/ · https://www.softwareimprovementgroup.com/eu-ai-act-summary/
- Fin de vie de Promtail et passage à Alloy : https://community.grafana.com/t/promtail-is-now-end-of-life-eol-how-to-migrate-to-grafana-alloy-for-existing-loki-server-deployments/162087
- Licences RF-DETR / YOLO : https://roboflow.com/model-licenses/rf-detr · https://blog.roboflow.com/roboflow-vs-ultralytics/
- Datasets de composants : https://data.mendeley.com/datasets/x5thzmkxhy/1 · https://universe.roboflow.com/eneb341-lab11-fxooq/eneb341-lab11-noubt · https://universe.roboflow.com/hamim-ixooj/deteksi_komponen_lengkap
- Modèles vision Ollama : https://localaimaster.com/blog/best-local-vision-models · https://docs.photoprism.app/user-guide/ai/ollama-models/
- Quotas Gemini (variables, à vérifier dans AI Studio) : https://tinkerllm.com/blog/gemini-api-free-tier-limits-rate-quotas/
- BigQuery dataset GitHub : https://console.cloud.google.com/marketplace/details/github/github-repos
