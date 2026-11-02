# Monitoring MicroForge (C11 modèle, C20 application)

`docker compose --profile monitoring up -d` (dossier `microforge/infra`), puis :

| Outil | URL | Rôle |
|---|---|---|
| Grafana | http://localhost:3000 | tableaux de bord « Application » et « Modèle de vision », alertes Discord |
| Prometheus | http://localhost:9090 | métriques + règles d'alerte (`prometheus/alerts.yml`) |
| Loki + Alloy | via Grafana > Explore | journaux JSON des conteneurs (filtre `{service="api_ia"}`) |
| Uptime Kuma | http://localhost:3001 | sondes HTTP `/health` des API et `/_stcore/health` de Streamlit |

## Seuils
| Métrique | Seuil | Réaction |
|---|---|---|
| Disponibilité API | 0 pendant 1 min | alerte critique |
| Latence p95 | > 2 s pendant 5 min | avertissement |
| Erreurs 5xx | > 2 % pendant 5 min | alerte critique |
| Taux de corrections (modèle) | > 25 % sur 7 j | réentraînement (`repository_dispatch: retrain`) |
| Confiance moyenne | < 0,5 sur 24 h | enquête dérive |
| Objets hors catalogue | > 20 % sur 6 h | enrichir catalogue / dataset |

## Bac à sable (C11 : tester la chaîne avant la production)
`uv run python microforge/monitoring/traffic_generator.py --drift` envoie des photos synthétiques
et des retours « wrong_label » pour vérifier que l'alerte `TauxCorrectionsEleve` se déclenche.
