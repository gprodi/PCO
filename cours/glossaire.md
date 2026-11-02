# Glossaire de la sécurité d'API

Petit dictionnaire des termes utilisés dans le tutoriel. À garder ouvert pendant les exercices.

| Terme | Définition courte |
|-------|-------------------|
| **Authentification (AuthN)** | Prouver QUI on est (ex : login + mot de passe). Répond à « es-tu bien toi ? ». |
| **Autorisation (AuthZ)** | Décider CE QU'ON A LE DROIT de faire (ex : un admin peut supprimer un user, pas un visiteur). Répond à « as-tu le droit ? ». |
| **API stateless** | Le serveur ne garde aucune session en mémoire. Chaque requête porte sa preuve d'identité (le token). Indispensable pour passer à l'échelle. |
| **Token** | Jeton remis au client après login, qu'il renvoie à chaque requête pour prouver son identité. |
| **JWT (JSON Web Token)** | Format de token standard composé de 3 parties séparées par des points : `header.payload.signature`. Lisible par tous, mais infalsifiable sans la clé. |
| **Header (JWT)** | 1re partie du JWT. Indique l'algorithme de signature (ex : `HS256`) et le type (`JWT`). |
| **Payload (JWT)** | 2e partie du JWT. Contient les **claims** (données : identité, expiration...). Encodé en base64url, donc LISIBLE. Ne jamais y mettre de secret. |
| **Signature (JWT)** | 3e partie du JWT. Garantit que le token n'a pas été modifié. Calculée avec la `SECRET_KEY`. |
| **Claim** | Une information dans le payload. Standards : `sub` (sujet/identité), `exp` (expiration), `iat` (émis le), `iss` (émetteur). |
| **base64url** | Encodage (pas un chiffrement !) qui transforme des octets en texte URL-safe. Réversible par n'importe qui. |
| **HS256** | Signature symétrique : la MÊME clé secrète sert à signer et à vérifier. Simple, idéal pour une seule API. |
| **RS256** | Signature asymétrique : clé privée pour signer, clé publique pour vérifier. Utile quand plusieurs services doivent vérifier sans pouvoir signer. |
| **SECRET_KEY** | Clé secrète du serveur servant à signer les JWT. Si elle fuite, n'importe qui peut forger des tokens. Jamais en dur dans le code, jamais sur Git. |
| **OAuth2** | Cadre standard de délégation d'accès. Définit plusieurs « flux » (grants). |
| **Password Grant** | Flux OAuth2 où l'utilisateur échange directement `username` + `password` contre un token. Adapté quand le client est de confiance (ton propre front). |
| **Bearer token** | « Token au porteur » : quiconque le détient peut l'utiliser. Envoyé via l'en-tête `Authorization: Bearer <token>`. |
| **Access token** | Token de courte durée (ex : 15 min) présenté à chaque requête pour accéder aux ressources protégées. |
| **Refresh token** | Token de longue durée (ex : 7 jours) servant UNIQUEMENT à obtenir un nouvel access token, sans redemander le mot de passe. |
| **Rotation de refresh token** | À chaque rafraîchissement, l'ancien refresh token est invalidé et un nouveau est émis. Limite les dégâts en cas de vol. |
| **Révocation** | Rendre un token invalide avant son expiration (ex : au logout). Nécessite de garder une trace côté serveur (jti, liste noire...). |
| **jti** | « JWT ID » : identifiant unique d'un token, pratique pour le révoquer individuellement. |
| **Scope** | Périmètre de permission attaché à un token (ex : `predict`, `admin`). Permet une autorisation fine. |
| **Rôle** | Catégorie d'utilisateur (ex : `user`, `admin`) servant à décider des droits. |
| **Hachage de mot de passe** | Transformation à sens unique du mot de passe avant stockage. On ne stocke JAMAIS le mot de passe en clair. bcrypt/argon2 sont les standards. |
| **bcrypt / argon2** | Algorithmes de hachage lents et salés, conçus pour résister aux attaques par force brute. |
| **401 Unauthorized** | Code HTTP : « je ne sais pas qui tu es » (token absent, invalide ou expiré). |
| **403 Forbidden** | Code HTTP : « je sais qui tu es, mais tu n'as pas le droit » (rôle/scope insuffisant). |
| **`Depends` (FastAPI)** | Mécanisme d'injection de dépendances de FastAPI. Sert à factoriser la logique d'authentification réutilisable. |
| **`/docs` (Swagger UI)** | Documentation interactive auto-générée par FastAPI. Permet de tester les endpoints, y compris le bouton « Authorize ». |

## Sécurité JWT avancée

| Terme | Définition courte |
|-------|-------------------|
| **`nbf`** | « Not before » : date avant laquelle le token n'est pas encore valide. Vérifié automatiquement par PyJWT s'il est présent. |
| **`aud` (audience)** | Destinataire prévu du token. N'est vérifié que si on passe `audience=...` au décodage : l'oublier laisse passer un token destiné à une autre API. |
| **`leeway`** | Tolérance d'horloge (en secondes) acceptée sur `exp`/`nbf` pour absorber les petits décalages entre serveurs. |
| **`alg:none`** | En-tête forgé déclarant « aucune » signature. Piège classique : d'anciennes librairies l'acceptaient. Défense : imposer une liste blanche d'algorithmes, ne jamais désactiver la vérification. |
| **Confusion d'algorithme** | Attaque RS256 → HS256 : l'attaquant forge un token HS256 en utilisant la clé publique (connue) comme secret HMAC. Défense : pinner l'algorithme attendu, ne jamais accepter une liste mixte. |
| **Liste blanche d'algorithmes** | Paramètre `algorithms=["HS256"]` au décodage : seul l'algorithme attendu est accepté. Règle de base de toute validation JWT. |

## OAuth2 en largeur & OpenID Connect

| Terme | Définition courte |
|-------|-------------------|
| **Resource Owner** | L'utilisateur, propriétaire des données. |
| **Client** | L'application qui demande l'accès (front web, mobile, autre service). |
| **Authorization Server** | Le « guichet » qui authentifie et délivre les tokens. |
| **Resource Server** | L'API qui héberge les ressources protégées et vérifie les tokens. |
| **Grant type** | Façon d'obtenir un token. Les principaux : Authorization Code + PKCE, Client Credentials, Password (ROPC). |
| **Authorization Code + PKCE** | Flux recommandé (OAuth 2.1) pour les apps web/mobile : un code à usage unique, protégé par PKCE, est échangé contre les tokens. |
| **PKCE** | « Proof Key for Code Exchange » : extension qui empêche l'interception du code d'autorisation. |
| **Client Credentials** | Flux service à service (machine-to-machine), sans utilisateur. |
| **Password Grant (ROPC)** | Échange direct identifiants → token. Simple mais **déconseillé par OAuth 2.1** ; utilisé ici par simplicité pédagogique. |
| **OAuth 2.1** | Consolidation d'OAuth 2.0 qui durcit les bonnes pratiques (PKCE obligatoire, suppression du flux Implicit, Password déconseillé). |
| **OpenID Connect (OIDC)** | Couche d'**identité** au-dessus d'OAuth2 : ajoute un `id_token` (JWT) qui dit QUI est l'utilisateur. OAuth2 = autorisation, OIDC = authentification. |
| **`id_token`** | Token OIDC (JWT) décrivant l'utilisateur authentifié (à distinguer de l'access token, qui sert l'autorisation). |

## Refresh avancé & stockage côté client

| Terme | Définition courte |
|-------|-------------------|
| **Famille de tokens** | Ensemble des refresh tokens issus d'une même session de connexion, suivis ensemble pour détecter les rejeux. |
| **Détection de réutilisation** | Repérer qu'un refresh token déjà « tourné » est rejoué : signe probable d'un vol. |
| **Révocation en cascade** | Conséquence de la détection : on invalide **toute la famille**, déconnectant aussi bien l'attaquant que la victime. |
| **localStorage** | Stockage navigateur accessible en JavaScript. Pratique mais vulnérable au **XSS** (un script injecté peut lire le token). |
| **Cookie httpOnly** | Cookie inaccessible au JavaScript : protège du XSS, mais envoyé automatiquement, donc exposé au **CSRF**. |
| **XSS** | « Cross-Site Scripting » : injection de script malveillant dans une page ; peut voler un token stocké en localStorage. |
| **CSRF** | « Cross-Site Request Forgery » : un site tiers déclenche une requête authentifiée via les cookies de la victime. Contré par `SameSite` + jeton anti-CSRF. |
| **`SameSite`** | Attribut de cookie limitant son envoi aux requêtes provenant du même site ; atténue le CSRF (`Strict`/`Lax`). |

## Durcissement & mise en production

| Terme | Définition courte |
|-------|-------------------|
| **Rate limiting** | Limiter le nombre de requêtes par client/IP sur une fenêtre de temps. Sur `/token`, casse le brute-force. |
| **Brute-force** | Attaque qui teste massivement des mots de passe. Contrée par le rate limiting et le hachage lent. |
| **429 Too Many Requests** | Code HTTP renvoyé quand une limite de débit (rate limit / quota) est dépassée. |
| **slowapi** | Bibliothèque de rate limiting pour FastAPI/Starlette. |
| **CORS** | « Cross-Origin Resource Sharing » : règles indiquant au navigateur quelles origines peuvent appeler l'API. On restreint aux origines de confiance (jamais `*` avec credentials). |
| **Énumération de comptes** | Déduire quels comptes existent via des messages ou des temps de réponse différents. Contrée par un message générique unique et une vérification de hash systématique. |
| **fail-closed** | Principe : en cas de configuration manquante (ex. `SECRET_KEY` absente), l'application **refuse de démarrer** plutôt que de tourner en mode dégradé/dangereux. |
| **En-têtes de sécurité** | En-têtes HTTP défensifs (HSTS, X-Content-Type-Options, etc.) ajoutés côté serveur/reverse proxy. |
| **OWASP API Security Top 10** | Liste de référence des 10 risques majeurs des API (API2 authentification, API4 consommation, API5 autorisation de fonction, API8 mauvaise configuration...). |
| **MFA** | Authentification multi-facteur : ajoute un second facteur (code, appli) au mot de passe. |

## Spécifique IA (serving de modèle)

| Terme | Définition courte |
|-------|-------------------|
| **Quota par utilisateur** | Nombre maximal d'appels autorisés par compte (par fenêtre de temps). Maîtrise le coût et l'abus d'un endpoint de modèle. |
| **Validation métier stricte** | Contraindre les entrées du modèle à des **bornes réalistes** (pas seulement « positif ») pour rejeter les valeurs aberrantes ou adversariales. |
| **Extraction de modèle** | Attaque consistant à reconstituer un modèle en l'interrogeant massivement. Freinée par les quotas et la limitation d'usage. |
| **Injection de prompt** | Menace propre aux LLM : l'entrée utilisateur « écrase » les consignes système car elles partagent le même canal de texte. Défense en profondeur (séparer, borner, filtrer). |
| **Chaîne d'approvisionnement (modèle)** | Risque lié au chargement d'un modèle non fiable : `joblib.load` peut exécuter du code. Ne charger que des artefacts de confiance. |
