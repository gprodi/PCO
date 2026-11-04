# MicroForge — application web installable (PWA)

Interface des utilisateurs de MicroForge, pensée d'abord pour le téléphone : on photographie son
stock à l'atelier, on choisit une idée de projet et on suit le câblage écran en main.
L'application Streamlit (`src/microforge/app_streamlit`) reste la preuve de concept.

| Vue | Ce qu'elle fait | API appelée |
|---|---|---|
| Connexion | création de compte, connexion, déconnexion | `api_data` `/v1/auth/*` |
| Mon stock | ajout par carte ou composant, quantité, emplacement ; total des pièces | `api_data` `/v1/inventory*` |
| Photo | photo prise par l'appareil (`capture="environment"`), pièces reconnues ajoutées en un geste | `api_ia` `/v1/vision/scan` |
| Idées | projets réalisables avec le stock, pièces manquantes | `api_ia` `/v1/builds/suggest` |
| Projet | câblage, schéma, code, nomenclature, contrôle électrique | `api_ia` `/v1/builds/generate` |
| Copilote | question sur le catalogue et le stock, réponse avec ses sources | `api_ia` `/v1/copilot/ask` |

## Choix techniques

- **React 19 + Vite 8**, sans bibliothèque d'interface : les jetons de couleur, les polices
  auto-hébergées (licence OFL) et les contrastes sont ceux de la démo et du thème Streamlit.
- **Jetons** : jeton d'accès en mémoire, jeton de rafraîchissement dans `sessionStorage` (le temps de
  l'onglet). Sur une réponse 401, le client renouvelle les jetons puis rejoue la requête
  (`src/api.js`, testé par Vitest).
- **Hors ligne** : service worker écrit à la main (`public/sw.js`). L'interface et ses fichiers sont
  mis en cache à l'installation (liste produite par le plugin `precache` de `vite.config.js`, nom de
  cache versionné par empreinte). Les appels aux API ne sont jamais mis en cache : hors ligne,
  l'application le dit au lieu d'afficher des données périmées.
- **Configuration au lancement** : `config.js` est lu avant l'application. La même construction sert
  en local, en CI et en préproduction ; seul `config.js` change (servi par nginx depuis les
  variables `MF_PUBLIC_API_DATA_URL` et `MF_PUBLIC_API_IA_URL`).
- **Sécurité** : politique CSP stricte dans l'image nginx (`nginx/securite.inc.template`) — aucun
  script en ligne, `connect-src` limité aux deux API, `frame-ancestors 'none'`. Le parcours E2E
  tourne avec ces en-têtes : une ressource bloquée fait échouer le test.
- **Accessibilité** : lien d'évitement, navigation au clavier, onglets ARIA, zones défilantes
  focalisables, libellés sur chaque champ. Chaque vue est auditée par axe-core (WCAG 2.2 A/AA)
  pendant le parcours E2E.

## Lancer en local

Avec la pile Docker (API + PWA + Streamlit + PostgreSQL) :

```bash
cd microforge/infra
docker compose --profile core up -d --build
```

La PWA est sur http://localhost:5173.

En développement (rechargement à chaud), avec les deux API lancées sur 8000 et 8001 :

```bash
cd microforge/pwa
npm ci
npm run dev
```

`npm ci` utilise `.npmrc` (`legacy-peer-deps`) : `@vitejs/plugin-react` ne déclare pas encore Vite 8
dans ses dépendances pairs.

## Tests

```bash
npm test
```

Tests unitaires du client d'API (Vitest) : connexion, renouvellement du jeton, erreurs FastAPI,
envoi de la photo, pagination du catalogue, stockage indisponible.

Parcours de bout en bout (depuis la racine du dépôt, après `npm run build`) :

```bash
uv run pytest -m e2e microforge/tests/test_e2e_parcours.py -k pwa
```

Le test démarre `api_data` et `api_ia` (SQLite, clés JWT éphémères, modèle de langage simulé), sert
`dist/` avec les en-têtes de l'image nginx, puis `e2e/parcours-pwa.cjs` enchaîne au format
téléphone : inscription → stock → idées → projet (5 onglets) → copilote → photo, audit axe de
chaque vue, puis rechargement hors ligne depuis le service worker.

## Image Docker

```bash
docker build -t microforge-pwa microforge/pwa
docker run -p 5173:8080 -e MF_PUBLIC_API_DATA_URL=https://api.exemple.org -e MF_PUBLIC_API_IA_URL=https://ia.exemple.org microforge-pwa
```

Construction en deux étapes : Node 24 (tests Vitest puis `vite build`), puis nginx 1.30 (branche
stable) qui sert les fichiers. En préproduction, Traefik publie la PWA sur `app.<domaine>`
(`infra/docker-compose.edge.yml`) ; les deux API n'acceptent que cette origine (CORS).

## Reste à faire

- Lecture de la carte par WebSerial (US8) : téléverser le code généré depuis le navigateur.
- Mesure Lighthouse (performances, PWA) sur la préproduction, une fois le serveur choisi.
