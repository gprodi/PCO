# Conformité RGPD (C4)

## Registre des traitements
| Traitement | Finalité | Base légale | Données | Durée de conservation | Destinataires | Sécurité |
|---|---|---|---|---|---|---|
| Comptes utilisateurs | authentification, service | exécution du contrat | pseudo, e-mail (chiffré Fernet), ville (facultative), mot de passe (argon2) | jusqu'à suppression ; inactifs > 24 mois supprimés | aucun tiers | chiffrement, index aveugle HMAC, TLS |
| Photos d'inventaire | identifier les composants | exécution du contrat | image (non conservée), empreinte SHA-256, dimensions | métadonnées 30 jours | LLM local ; Gemini/Claude seulement en secours (hors UE — mentionné) | EXIF/GPS supprimés avant tout envoi |
| Retours de détection | amélioration du modèle | intérêt légitime | composant prédit/corrigé, confiance | 13 mois | aucun tiers | pseudonymisé (id) |
| Journaux techniques | sécurité, supervision | intérêt légitime | id utilisateur, id de requête, chemin, statut | 6 mois | aucun tiers | aucune donnée nominative dans les logs |
| Entraînement du modèle | améliorer la vision | consentement (case à cocher) | découpes anonymes de composants | jusqu'au retrait du consentement | aucun tiers | — |

## Droits des personnes
- Accès / portabilité : `GET /v1/users/me/export` (JSON complet) ; bouton dans « Mon compte ».
- Effacement : `DELETE /v1/users/me` (cascade complète).

## Procédure de tri (automatisée, hebdomadaire)
`uv run mf-pipeline purge` (flow Prefect planifié le dimanche 3 h) : photos expirées, retours > 13 mois,
jetons expirés/révoqués, comptes inactifs > 24 mois. Chaque exécution est tracée (`execution_collecte`).
