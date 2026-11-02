# Tests automatisés du modèle (C12)

| Partie | Cas testés | Outil | Fichier |
|---|---|---|---|
| Format des données | lignes YOLO (5 valeurs, classe connue, coordonnées normalisées) | pytest paramétré | `tests/test_ml_data.py` |
| Complétude / labellisation | label manquant, image négative, classes sous-représentées | pytest | idem |
| Fuites et doublons | même image (SHA-256) dans deux splits | pytest | idem |
| Cohérence des classes | `dataset.yaml` = `classes.yaml` = identifiants du catalogue | pytest | idem |
| Entraînement | test fumée 1 epoch CPU (`train.py --smoke`) | CI (job GPU optionnel) | `ml/train.py` |
| Évaluation / validation | porte de non-régression (mAP50 ≥ production − 0,02), rapport | pytest | `ml/evaluate.py` |
| Inférence | schéma de sortie, mapping classes → catalogue, affinage VLM | pytest + `StaticDetector` | `tests/test_api_ia.py` |

Données versionnées avec **DVC** (remote S3 SeaweedFS) ; couverture mesurée par `pytest --cov` (seuil 80 %).
```bash
uv run pytest microforge/tests/test_ml_data.py -q
uv run --extra ml python microforge/ml/train.py --smoke
```
