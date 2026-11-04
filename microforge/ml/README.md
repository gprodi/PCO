# ml/ — Détecteur de composants (E3 : C11, C12, C13)

| Étape | Commande | Machine conseillée |
|---|---|---|
| Préparer le dataset (fusion des sources, remappage, split sans fuite, EXIF retiré) | `uv run python microforge/ml/prepare.py --sources microforge/data/sources --out microforge/data/dataset --remplacer` | toutes |
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
| **Roboflow Universe** — 8 jeux téléchargés par Gaël (CC BY 4.0, lus dans les README des exports) | **5 retenus** (correspondances dans `sources/*.yaml`) ; 2 exports « folder » écartés (classification, sans boîtes) ; `arduino-wf8el` écarté (détection de pièces manquantes, autre tâche). Préparés sur le PC de Gaël : 10 063 images (6 744 / 1 904 / 1 415), validation OK. |

### Assez de données ?
D'après le [guide de collecte et d'annotation d'Ultralytics](https://docs.ultralytics.com/guides/data-collection-and-annotation/)
(relu le 04/11/2026 dans le dépôt `ultralytics/ultralytics`) : « quelques centaines d'objets annotés par
classe » suffisent pour démarrer en transfert d'apprentissage ; pour une performance fiable en conditions
réelles, **≥ 1 500 images et ≥ 10 000 objets annotés par classe**. Sur IoTKITs, quelques centaines de cartes
par classe ont donné les scores ci-dessous (photos propres, même origine que la validation). Objectif retenu pour MicroForge : **≥ 150 objets par
classe en entraînement et ≥ 30 en validation et en test** (sinon le score de la classe n'est pas mesurable).
`stats.json` donne ces comptes ; une classe sous l'objectif reçoit des photos personnelles ou un jeu de plus.

Mesuré le 04/11 sur les 5 jeux Roboflow (16 classes présentes sur 51), objets train / val / test :

| Situation | Classes |
|---|---|
| Objectif atteint | `resistor` (4 085 / 989 / 331), `push_button`, `nodemcu`, `transistor`, `servo_sg90`, `hc_sr04`, `led`, `arduino_uno`, `potentiometer` |
| Trop peu en test | `capacitor_electrolytic` (10), `capacitor_ceramic` (15), `diode` (0) |
| Trop peu en entraînement | `breadboard` (91 ; 468 en test : une longue série de photos semblables, corrigé ci-dessous), `diode` (87) |
| Presque vides | `trimmer` (19 / 5 / 3), `screw_terminal` (6 / 5 / 0), `crystal` (3 / 0 / 0) |
| Aucune image, même avec IoTKITs (7 cartes de plus) | **28 classes** : Pico, LED RVB, buzzer, DHT11, DHT22, DS18B20, PIR, LDR, humidité du sol, MQ-2, MPU6050, BME280, RTC, OLED, LCD 1602, afficheur 7 segments, relais, L298N, moteur pas à pas, moteur CC, anneau NeoPixel, clavier 4×4, RFID RC522, joystick, encodeur rotatif, module SD, HX711, fils Dupont |

Le jeu « kit Arduino » (sem2l1) devait fournir LCD 1602, moteur CC, buzzer et fils Dupont : aucun de ses
objets n'est arrivé. Cause probable : annotations en polygones, que `prepare.py` ignorait. Elles sont
désormais converties en boîtes, et `stats.json` détaille chaque source (`par_source`,
`polygones_convertis`, `images_labels_illisibles`, `plus_gros_groupes`). Les groupes sont maintenant placés
du plus gros au plus petit : une longue série de photos semblables part en entraînement au lieu de remplir le
test.

### Premier entraînement de référence (04/11/2026, runner GitHub, CPU)

YOLO11n pré-entraîné, 15 epochs, 416 px, lot de 16, sur **IoTKITs seul** (8 classes de cartes) ; 32 min sur
CPU AMD EPYC (workflow `jeux-de-donnees`, run 41781341808). Mesures sur le split de **validation**
(272 images, 213 cartes) — c'est aussi lui qui choisit le meilleur epoch, donc légèrement optimiste :

| Classe | mAP50 | mAP50-95 |
|---|---|---|
| **toutes** | **0,965** | **0,943** (précision 0,894, rappel 0,955) |
| arduino_uno | 0,995 | 0,995 |
| arduino_mega | 0,995 | 0,995 |
| arduino_leonardo | 0,990 | 0,990 |
| arduino_micro | 0,981 | 0,949 |
| arduino_due | 0,963 | 0,947 |
| arduino_nano | 0,954 | 0,898 |
| esp32_devkit | 0,941 | 0,925 |
| arduino_pro_mini | 0,905 | 0,843 |

Inférence : 33,6 ms par image sur CPU. **À faire** : score sur le split de test (relance du workflow après
correction du chemin des résultats), puis sur les photos réelles de Gaël, seul test représentatif de l'usage.
Ces chiffres valent pour des photos de cartes seules et bien cadrées ; les modules, capteurs et passifs
viennent des jeux Roboflow préparés sur le PC de Gaël (`importer_zips.py`).

Chaîne : `fetch_mendeley.py` (licence vérifiée) → `coco_to_yolo.py` → `prepare.py` (correspondance des classes
dans `sources/*.yaml`, groupes sans fuite, EXIF retiré, `manifest.json`) → `dataset_checks.py` (C12).

## Licence du modèle
Ultralytics YOLO est sous **AGPL-3.0** : compatible avec un dépôt public. Alternative comparée
dans le benchmark C7 : RF-DETR (Apache 2.0, tailles N/S/M/L).
