# 🔧 MicroForge

**De la photo de ton stock électronique au montage soudé, programmé et simulé.**
Projet de fin d'études — Développeur en IA (RNCP37827, Simplon) — Gaël Prodi.

1. 📷 **Photographie ton stock** : un détecteur YOLO entraîné et un modèle vision-langage (local d'abord) reconnaissent et comptent les composants.
2. 💡 **Que puis-je construire ?** : 31 modèles de projets classés selon ton stock (et des idées générées par IA).
3. 🛠️ **Je veux construire…** : décris ton idée ; l'IA choisit des composants du catalogue, MicroForge fait le reste.
4. 📦 Pour chaque projet : **tableau et schéma de câblage**, **guide de soudure pas-à-pas**, **firmware Arduino/ESP32/Pico**, **simulation Wokwi**, **netlist KiCad**, **nomenclature** et **liste d'achat chiffrée**.

> Principe de fiabilité : **le LLM ne choisit jamais une broche**. Un allocateur déterministe câble,
> un contrôle électrique (ERC) vérifie (niveaux 3,3 V/5 V, courant, broches de démarrage, ADC2/Wi-Fi…)
> et ajoute automatiquement résistances série, pull-ups et ponts diviseurs.

## Démarrage rapide
```bash
uv sync --all-packages --group dev --extra data --extra app
uv run llm-gateway doctor                       # profil matériel et modèles conseillés
uv run microforge suggest --stock "esp32=1,dht22=1,oled=1,led=3"
uv run microforge build station-meteo-oled --board esp32-devkit-v1 --out build
docker compose -f microforge/infra/docker-compose.yml --profile core up -d --build   # depuis la racine du dépôt
```
Application (PWA) : http://localhost:5173 · preuve de concept Streamlit : http://localhost:8501 · API données : http://localhost:8000/docs · API IA : http://localhost:8001/docs

## Organisation
| Dossier | Contenu | Épreuves |
|---|---|---|
| `pwa/` | application web installable (React 19 + Vite 8) : stock, photo, idées, projet, copilote ; service worker hors ligne, image nginx avec CSP, tests Vitest et parcours Playwright ([README](pwa/README.md)) | E3, E4 |
| `src/microforge/core` | catalogue (40 cartes, 103 composants, 80 projets), allocateur, ERC, firmware, sorties | E4 |
| `src/microforge/copilot` | copilote RAG : catalogue → 379 passages, index mémoire ou PostgreSQL + pgvector (HNSW cosinus), réponses citées, « je ne sais pas » sous le seuil, repli extractif sans LLM ; `POST /v1/copilot/ask`, page Streamlit « Copilote » | E3, E4 |
| `src/microforge/sim` | atelier virtuel : transpileur C++ → JavaScript (sous-ensemble des projets, temps virtuel), moteur `mfsim.js` et 55 modèles de composants, mode « Je branche » (`atelier.js`), page Streamlit « Atelier virtuel » | E4 |
| `src/microforge/data_pipeline` | collecte 5 types de sources, SQL, agrégation, import, purge RGPD | E1 |
| `src/microforge/api_data` | API données (JWT RS256, RGPD, OWASP) | E1, E4 |
| `src/microforge/api_ia` + `vision` | API du modèle (vision YOLO+VLM, génération) | E3 |
| `src/microforge/app_streamlit` | preuve de concept | E3, E4 |
| `ml/` | dataset, entraînement, évaluation, registre MLflow, DVC | E3 |
| `monitoring/` | Prometheus, Grafana, Loki/Alloy, alertes, bac à sable | E3, E5 |
| `infra/` | Docker Compose par profils, LiteLLM | E2, E4 |
| `veille/`, `benchmark/` | veille, benchmark des services d'IA | E2 |
| `docs/` | documentation Sphinx + dossiers E1 à E5 | toutes |
| Idées par thème | 145 idées en 17 thèmes (plantes, intérieur, extérieur, sécurité, robotique, jeux, temps, animaux, énergie…) : page Streamlit « Explorer par thème » et site de révision `/idees/` | E4 |

## Qualité
`uv run pytest --cov` (couverture > 90 %), `uv run ruff check .` ; firmwares vérifiés par `g++` (en-têtes simulés)
puis compilés par `arduino-cli` dans la CI.
