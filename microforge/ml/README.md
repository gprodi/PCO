# ml/ — Détecteur de composants (E3 : C11, C12, C13)

| Étape | Commande | Machine conseillée |
|---|---|---|
| Préparer le dataset (fusion Roboflow/Mendeley/photos, remappage, split sans fuite) | `uv run python -m ml.prepare --sources data/sources --out data/dataset` | toutes |
| Valider les données (C12) | `uv run pytest microforge/tests/test_ml_data.py` | toutes |
| Entraîner (profil matériel auto) | `uv run python microforge/ml/train.py --epochs 80` | PC bureau (GPU 8 Go) / Mac M4 (`mps`) |
| Évaluer + comparer à `@production` | `uv run python microforge/ml/evaluate.py --weights runs/detect/train/weights/best.pt` | toutes |
| Enregistrer dans MLflow (alias `@staging`) | `uv run python microforge/ml/register.py --run-id <id>` | toutes |
| Chaîne complète | `dvc repro` ou workflow GitHub `model-cd` | runner GPU |

Sans GPU : notebook `colab_train.ipynb` (Google Colab / Kaggle, GPU gratuit), puis `register.py` en local.

## Données
- Roboflow Universe : jeux Arduino/ESP32/breadboard/composants (licence **CC BY 4.0** à vérifier par jeu, citer les auteurs).
- Mendeley Data « IoT kits » (DOI 10.17632/x5thzmkxhy.1).
- Photos personnelles annotées avec Label Studio (export YOLO) — objectif 600–1 000 images.

## Licence du modèle
Ultralytics YOLO est sous **AGPL-3.0** : compatible avec un dépôt public. Alternative comparée
dans le benchmark C7 : RF-DETR (Apache 2.0, tailles N/S/M/L).
