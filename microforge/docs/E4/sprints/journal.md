# Journal du sprint en cours (point quotidien asynchrone)

Reconstitué à partir de l'historique Git (`git log`), des runs GitHub Actions et des incidents de
`docs/E5/incidents.md` : chaque ligne cite ce qui a réellement été livré ou corrigé ce jour-là.
Les commits sont co-signés par l'assistant de code utilisé pendant le développement (Claude Code).

## Sprint S0 — 02/11 → 15/11/2026 (fondations, cœur, API, preuve de concept, veille lancée)

### Lundi 02/11 — 28 commits
- **Fait** : monorepo (workspace uv, ruff, CI), passerelle LLM ; MicroForge : cœur déterministe
  (catalogue, allocateur de broches, ERC, firmware, sorties), API données et IA, pipeline E1 (5 types
  de sources), preuve de concept Streamlit, MLOps, supervision, infra ; catalogue de 40 cartes
  (11 familles) ; compilation réelle des firmwares en CI ; migrations Alembic ; site Révisions DevIA
  et 36 cours rédigés ; début du stockage vectoriel pgvector ; brouillons des rapports E1–E5.
- **Problèmes** (incidents 1 à 4, corrigés le jour même avec un test) : CI rouge (extras uv non
  installés, dossier d'installation d'arduino-cli absent) ; page « Explorer » en erreur (méthodes
  absentes du client) ; `compile-demo` prenait le dossier `wokwi/` pour le sketch ; constante SPI en
  collision avec une macro du cœur AVR.
- **Décision** : le modèle de Claude est retiré de la chaîne IA par défaut (pas d'abonnement) :
  Ollama local, puis Gemini gratuit.

### Mardi 03/11 — 18 commits
- **Fait** : compatibilité composant ↔ carte (Due, ESP32-C6, H2) ; RAG des cours et copilote
  MicroForge sur PostgreSQL + pgvector ; collecte réelle E1 (100 500 pièces LCSC, import PostgreSQL,
  workflow `collecte`) ; veille 2026-45 et outil `mf-veille` ; stock complet par valeur (étape 3) ;
  14 nouveaux projets (étape 5) ; atelier virtuel (étape 4) ; 9 boilerplates du site de révision.
- **Problèmes** : OneWire 2.3.8 refusé par les cœurs ESP32-C6 et H2 (vérifié en CI run 41) :
  `ds18b20` exclu de ces puces plutôt que masqué.

### Mercredi 04/11 — 26 commits
- **Fait** : E3 — jeux de données sous licence CC BY 4.0 (IoTKITs + 6 jeux Roboflow téléchargés par
  le runner), préparation sans fuite, deux entraînements CPU (test mAP50 0,974 sur 8 cartes,
  0,692 sur 27 classes), registre et comparaison des runs ; thème Streamlit ; audit axe-core
  (30 constats corrigés) ; diagrammes C4 ; parcours Playwright en CI ; Traefik (préproduction) ;
  PWA React + Vite servie par nginx.
- **Problèmes** (incidents 5 à 8) : chemin des résultats d'Ultralytics (`runs_dir`) et `| tee` qui
  masquait l'échec ; faux positif gitleaks sur un `.env.example` ; polygones ignorés sans signalement
  par `prepare.py` ; ordre de `rglob` non garanti (échec seulement sous Python 3.12). Hors incident :
  un run lancé avant la création du secret Roboflow ne le voyait pas ; relancé ensuite.
- **Correction de cap** : des phrases des rapports décrivaient comme faits des éléments encore à
  construire (DVC, PWA, parcours E2E) ; elles ont été réécrites, puis les éléments ont été construits.

### Jeudi 05/11
- **Fait** : MCD et MLD tracés avec Mocodo et vérifiés contre le schéma par un test ; mesure de
  l'effet des index sur la base réelle intégrée au workflow `collecte`.
