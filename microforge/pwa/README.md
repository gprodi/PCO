# MicroForge — application web installable (PWA)

Interface des utilisateurs de MicroForge, pensée d'abord pour le téléphone : on photographie son
stock à l'atelier, on choisit une idée de projet et on suit le câblage écran en main.
L'application Streamlit (`src/microforge/app_streamlit`) reste la preuve de concept.

| Vue | Ce qu'elle fait | API appelée |
|---|---|---|
| Connexion | création de compte, connexion, à côté de l'établi animé | `api_data` `/v1/auth/*` |
| Accueil | établi animé (Arduino Uno et chenillard de 3 LED, dessins Wokwi), état de l'atelier (pièces, projets réalisables), parcours en 7 étapes, vitrine de vrais projets | `api_ia` `/v1/ideas/inspiration`, `/v1/builds/suggest` |
| Explorer | 145 idées en 17 thèmes, chaque idée annotée avec le stock (pièces possédées ou manquantes, réalisable ou non), projets les plus proches du stock ; les 145 idées ont un modèle vérifié et se génèrent directement (une idée ajoutée sans modèle se conçoit avec l'IA : montage contrôlé par le moteur ; sans IA disponible, modèle le plus proche, signalé sur la page du projet) | `api_ia` `/v1/ideas/explore`, `/v1/builds/suggest`, `/v1/builds/from-goal` |
| Créer | comme la page Streamlit « Je veux construire… » : décrire son idée (l'IA choisit les composants, le moteur câble et contrôle ; sans IA, modèle le plus proche, signalé) ou choisir l'un des 145 modèles ; carte imposée ou choisie par MicroForge ; projets enregistrés (rouvrir, supprimer) | `api_ia` `/v1/builds/from-goal`, `/v1/builds/generate` ; `api_data` `/v1/templates`, `/v1/projects*` |
| Atelier | comme la page Streamlit « Atelier virtuel » : un projet, une carte compatible, brancher chaque composant puis simuler ; code JavaScript de la simulation consultable | `api_ia` `/v1/builds/generate` |
| Mon stock | pièces rangées par catégorie, ajout, retrait | `api_data` `/v1/inventory*` |
| Photo | photo prise par l'appareil (`capture="environment"`), pièces reconnues ajoutées en un geste | `api_ia` `/v1/vision/scan` |
| Projet | 9 onglets comme la démo : câblage (couleur de chaque fil Dupont), **atelier virtuel** (brancher puis simuler), schéma, code, guide de soudure, simulation Wokwi, nomenclature, KiCad, fiabilité et sources ; notions, difficulté et contrôle électrique en tête ; choix de la carte (cartes compatibles), archive .zip du projet (y compris conçu par l'IA), enregistrement dans « Mes projets » et liste d'achat (ce qui manque au stock, chiffré avec les offres collectées) ; provenance affichée pour un projet demandé à l'IA | `api_ia` `/v1/builds/generate`, `/v1/builds/bundle` ; `api_data` `/v1/projects`, `/v1/shopping-list` |
| Copilote | conversation : questions sur les composants et les cartes, réponses avec leurs sources | `api_ia` `/v1/copilot/ask` |

Navigation : barre en haut sur ordinateur, barre d'onglets en bas sur téléphone (Accueil, Explorer,
Créer, Atelier, Mon stock, Copilote) ; la photo s'ouvre depuis le stock et l'accueil, la page d'un
projet depuis Explorer, Créer ou l'Atelier.

## Choix techniques

- **React 19 + Vite 8**, sans bibliothèque d'interface ; dessins de la carte et des LED de l'établi : `@wokwi/elements` 1.9.2 (MIT). Par ailleurs : les jetons de couleur, les polices
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
  script en ligne, `connect-src` limité aux deux API, `frame-ancestors 'none'`. Seuls les attributs
  `style` sont permis en ligne (`style-src-attr`), pour les dessins Wokwi de l'établi. Le parcours E2E
  tourne avec ces en-têtes : une ressource bloquée fait échouer le test.
- **Atelier virtuel isolé** : le simulateur (`mfsim.js`) exécute la logique du projet avec
  `new Function`, interdit par la CSP de l'application. Il tourne donc dans un cadre à part,
  `public/atelier/`, chargé avec `<iframe sandbox="allow-scripts">` : origine opaque, donc ni jetons,
  ni stockage, ni API de l'application. La page lui envoie le projet par `postMessage` (messages
  filtrés sur la fenêtre d'origine des deux côtés) ; le cadre renvoie sa hauteur. Sa propre CSP
  (`nginx/atelier.inc.template`) autorise `unsafe-eval` **dans ce cadre seulement**, interdit toute
  requête réseau (`connect-src 'none'`) et ne se laisse afficher que par l'application
  (`frame-ancestors 'self'` ; Traefik : `SAMEORIGIN` sur `/atelier/` seulement). Les scripts sont des
  copies de `src/microforge/sim/static` (un test vérifie qu'elles sont identiques) ; les dessins
  Wokwi sont copiés depuis `node_modules` à la construction.
- **Guide de soudure** : Markdown rendu par `marked` 15.0.12 (`src/markdown.js`), HTML brut échappé,
  liens limités à http(s).
- **Accessibilité** : lien d'évitement, navigation au clavier, onglets ARIA, zones défilantes
  focalisables, libellés sur chaque champ. Chaque vue est auditée par axe-core (WCAG 2.2 A/AA)
  pendant le parcours E2E.

## Lancer en local

Avec la pile Docker (API + PWA + Streamlit + PostgreSQL) :

```bash
docker compose -f microforge/infra/docker-compose.yml --profile core up -d --build
```

(depuis la racine du dépôt ; ou `cd microforge/infra` puis la même commande sans `-f …`).
Docker Desktop doit être démarré et Compose en v2.24 ou plus ; erreurs fréquentes et remèdes :
README racine, « Si la commande `up` échoue ».

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

Tests unitaires (Vitest) : client d'API (connexion, renouvellement du jeton, erreurs FastAPI,
envoi de la photo, pagination du catalogue, archive .zip, stockage indisponible) et rendu Markdown
du guide (HTML échappé, liens non http neutralisés).

Parcours de bout en bout (depuis la racine du dépôt, après `npm run build`) :

```bash
uv run pytest -m e2e microforge/tests/test_e2e_parcours.py -k pwa
```

Le test démarre `api_data` et `api_ia` (SQLite, clés JWT éphémères, modèle de langage simulé), sert
`dist/` avec les en-têtes de l'image nginx, puis `e2e/parcours-pwa.cjs` enchaîne au format
téléphone : inscription → stock → idées → projet (9 onglets ; dans l'atelier, « Tout brancher » puis
la simulation avance ; archive .zip téléchargée ; changement de carte) → copilote → photo, audit axe
de chaque vue et du cadre de l'atelier, puis rechargement hors ligne depuis le service worker.

La même PWA est aussi testée dans sa **vraie image nginx** : le job CI « Pile complète » construit
la pile Docker (profils `core` et `monitoring`) et lance ce parcours contre http://localhost:5173
(CSP réelles, PostgreSQL, réseau compose, copilote sans modèle d'IA).

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
