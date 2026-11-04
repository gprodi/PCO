# ml/ — Détecteur de composants (E3 : C11, C12, C13)

| Étape | Commande | Machine conseillée |
|---|---|---|
| Préparer le dataset (fusion des sources, remappage, split sans fuite, EXIF retiré) | `uv run python microforge/ml/prepare.py --sources data/sources --out data/dataset` | toutes |
| Valider les données (C12) | `uv run pytest microforge/tests/test_ml_data.py` | toutes |
| Entraîner (profil matériel auto) | `uv run python microforge/ml/train.py --epochs 80` | PC bureau (GPU 8 Go) / Mac M4 (`mps`) |
| Évaluer + comparer à `@production` | `uv run python microforge/ml/evaluate.py --weights runs/detect/train/weights/best.pt` | toutes |
| Enregistrer dans MLflow (alias `@staging`) | `uv run python microforge/ml/register.py --run-id <id>` | toutes |
| Chaîne complète | `dvc repro` ou workflow GitHub `model-cd` | runner GPU |

Sans GPU : notebook `colab_train.ipynb` (Google Colab / Kaggle, GPU gratuit), puis `register.py` en local.

## Données
Le conteneur de développement n'atteint ni Hugging Face ni Mendeley : l'inspection et le téléchargement se
font sur un runner GitHub (workflow `jeux-de-donnees`), qui publie licence, catégories et statistiques.

| Source | Statut (04/11/2026) |
|---|---|
| **IoTKITs** — Mendeley Data, DOI 10.17632/x5thzmkxhy.1 ; article *Data in Brief* (2025, PMC12149570) | **retenu** : licence CC BY 4.0 confirmée par l'API Mendeley et par l'article ; 3 200 images, 32 classes de cartes et kits, export COCO Roboflow. Une partie des images vient de Kaggle et Roboflow Universe (signalé par les auteurs) : attribution dans `ATTRIBUTION.md`. |
| Roboflow 100 « circuit-elements » (CC BY 4.0) | écarté : photos de cartes électroniques (CMS), pas de modules |
| PCB object detection (MIT) | écarté : images hébergées sur Roboflow seulement, même domaine CMS |
| **Photos personnelles** (~30 composants) | protocole : [`PHOTOS.md`](PHOTOS.md) ; servent de test réel (composants jamais vus) et d'adaptation |

Chaîne : `fetch_mendeley.py` (licence vérifiée) → `coco_to_yolo.py` → `prepare.py` (correspondance des classes
dans `sources/*.yaml`, groupes sans fuite, EXIF retiré, `manifest.json`) → `dataset_checks.py` (C12).

## Licence du modèle
Ultralytics YOLO est sous **AGPL-3.0** : compatible avec un dépôt public. Alternative comparée
dans le benchmark C7 : RF-DETR (Apache 2.0, tailles N/S/M/L).
