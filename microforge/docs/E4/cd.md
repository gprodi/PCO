# Livraison continue (C19)

Fichier `.github/workflows/cd.yml` — déclenché sur `main`, les tags `v*` et à la demande.

1. **Packaging** : images Docker multi-architecture (amd64 + arm64 pour le Mac M4) des cibles
   `api_data`, `api_ia`, `streamlit` → GHCR, avec SBOM et cache de build.
2. **Tests fumée** : démarrage de la pile `core` et contrôle des `/health`.
3. **Livraison** : PR de release automatique (release-please : changelog + version) ; sa fusion crée le tag
   et la release GitHub.

Déploiement préprod : `MF_IMAGE_TAG=<tag> docker compose --profile core pull && docker compose --profile core up -d`.
Retour arrière : relancer avec le tag précédent.
