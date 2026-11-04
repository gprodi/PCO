# Livraison continue (C19)

Fichier `.github/workflows/cd.yml` — déclenché sur `main`, les tags `v*` et à la demande.

1. **Packaging** : images Docker multi-architecture (amd64 + arm64 pour le Mac M4) des cibles
   `api_data`, `api_ia`, `streamlit` → GHCR, avec SBOM et cache de build.
2. **Tests fumée** : démarrage de la pile `core` et contrôle des `/health`.
3. **Livraison** : PR de release automatique (release-please : changelog + version) ; sa fusion crée le tag
   et la release GitHub.

## Préproduction derrière Traefik (`infra/docker-compose.edge.yml`)

Traefik v3.7.16 se place devant l'application : HTTPS avec certificats Let's Encrypt (défi TLS),
redirection HTTP → HTTPS, en-têtes de sécurité (HSTS un an, `nosniff`, interdiction de l'affichage en
cadre, politique de référent). Seuls les ports 80 et 443 de Traefik sont ouverts ; l'application et
les deux API n'exposent plus de port.

| Adresse | Service |
|---|---|
| `https://app.<domaine>` | application Streamlit |
| `https://api.<domaine>` | api_data (comptes, stock, catalogue, projets) |
| `https://ia.<domaine>` | api_ia (vision, génération, copilote) |

1. Serveur Linux avec Docker ; DNS : `app.`, `api.` et `ia.` du domaine pointent vers lui.
2. `microforge/.env` : `MF_DOMAIN`, `ACME_EMAIL`, `MF_ENV=prod`, clés JWT et clé de chiffrement
   (`MF_JWT_PRIVATE_KEY`, `MF_JWT_PUBLIC_KEY`, `MF_FERNET_KEY`), `POSTGRES_PASSWORD`.
3. Lancer :
   ```bash
   cd microforge/infra
   MF_IMAGE_TAG=<tag> docker compose -f docker-compose.yml -f docker-compose.edge.yml --profile core --profile edge pull
   MF_IMAGE_TAG=<tag> docker compose -f docker-compose.yml -f docker-compose.edge.yml --profile core --profile edge up -d
   ```
4. Tests de fumée : `curl -fsS https://api.<domaine>/health` et `https://ia.<domaine>/health`, puis
   le parcours de bout en bout pointé sur `https://app.<domaine>`
   (`node microforge/tests/e2e/parcours.cjs https://app.<domaine> captures/`).

Retour arrière : relancer la commande 3 avec le tag précédent. Traefik lit le socket Docker en lecture
seule ; pour aller plus loin, un proxy de socket limité aux lectures. La configuration fusionnée est
vérifiée à chaque commit par `tests/test_infra_edge.py` (`docker compose config`).
