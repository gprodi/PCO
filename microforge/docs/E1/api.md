# API REST de mise à disposition (C5)

Documentation OpenAPI interactive : http://localhost:8000/docs (fichier : `/openapi.json`).

## Authentification et autorisation
- OAuth2 *password* : `POST /v1/auth/token` (pseudo ou e-mail) → JWT **RS256** (accès 15 min) + jeton de rafraîchissement (7 j).
- `POST /v1/auth/refresh` : rotation ; la réutilisation d'un jeton consommé révoque toute la famille.
- `POST /v1/auth/logout` : révocation. `GET /v1/auth/public-key` : clé publique pour l'API IA.
- Rôles : `user` (ses propres données) et `admin` (`/v1/admin/*`).

## Points de terminaison
| Méthode | Chemin | Rôle |
|---|---|---|
| POST | `/v1/auth/register` | inscription (5/min) |
| GET | `/v1/users/me`, `/v1/users/me/export` | profil, export RGPD |
| DELETE | `/v1/users/me` | effacement RGPD |
| GET | `/v1/components?q=&category=&limit=&offset=` | catalogue paginé (limite 200) |
| GET | `/v1/components/{id}`, `/v1/components/{id}/offers` | détail (broches, bibliothèques), offres triées par prix |
| GET | `/v1/boards`, `/v1/templates` | cartes, modèles de projets |
| CRUD | `/v1/inventory`, `/v1/inventory/bulk`, `/v1/inventory/summary` | stock (contrôle de propriété) |
| POST | `/v1/photos`, `/v1/feedback` | métadonnées de photo, retours de détection |
| CRUD | `/v1/projects` | projets sauvegardés |
| POST | `/v1/shopping-list` | liste d'achat chiffrée |
| GET/POST | `/v1/admin/ingestion-runs`, `/v1/admin/catalog/sync`, `/v1/admin/feedback-stats` | administration |

## OWASP API Security Top 10 (2023)
| Risque | Mesure |
|---|---|
| API1 BOLA | chaque objet vérifié par `user_id` ; 404 si étranger |
| API2 Authentification | argon2, anti-énumération, limitation 10/min sur `/token`, RS256 + liste blanche d'algorithmes |
| API3 Propriétés exposées | `response_model` stricts (jamais de hash/e-mail chiffré) |
| API4 Ressources | pagination plafonnée, taille d'upload 8 Mo, limitation de débit |
| API5 Fonctions | rôle admin obligatoire sur `/v1/admin/*` |
| API7 SSRF | aucune URL fournie par le client n'est appelée ; datasheets en liste blanche (pipeline) |
| API8 Configuration | CORS restreint, en-têtes `nosniff`, `DENY`, `no-store` |
| API9 Inventaire | versionnement `/v1`, OpenAPI à jour |
| API10 API tierces | réponses fournisseurs validées et normalisées (C3) |

## Accès direct à la base
Rôle PostgreSQL `analyst` en **lecture seule** :
```sql
CREATE ROLE analyst LOGIN PASSWORD '***';
GRANT CONNECT ON DATABASE microforge TO analyst;
GRANT USAGE ON SCHEMA public TO analyst;
GRANT SELECT ON composant, categorie, fabricant, offre, fournisseur, bibliotheque, utilise TO analyst;
```
Chaîne : `postgresql://analyst:***@localhost:5432/microforge` (tables utilisateurs non accessibles).
