# Chaîne de livraison continue du modèle (C13)

Fichier : `.github/workflows/model-cd.yml`.

```mermaid
flowchart LR
  T[Déclencheurs\npush ml/**, *.dvc\nretrain (alerte)\nmanuel, mensuel] --> D[Tests des données\nubuntu]
  D --> TR[Entraînement\nrunner GPU auto-hébergé\nMLflow]
  TR --> E[Évaluation\nporte de non-régression\nrapport + matrice de confusion]
  E -->|ok| R[Registre MLflow\n@staging]
  R --> PR[PR « Modèle vX »\nrapport joint]
  PR -->|fusion| P[Promotion @production\napi_ia recharge par alias]
```

| Déclencheur | Usage |
|---|---|
| `push` sur `microforge/ml/**` ou `*.dvc` | nouveau code ou nouvelles données |
| `repository_dispatch: retrain` | envoyé par l'alerte Grafana (taux de corrections) |
| `workflow_dispatch` | manuel (nombre d'epochs paramétrable) |
| `schedule` mensuel | réentraînement de routine |

Installation du runner GPU (PC bureau) : *Settings > Actions > Runners > New self-hosted runner*,
labels `self-hosted, gpu`. Secrets : `MLFLOW_TRACKING_URI`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_ENDPOINT`.
