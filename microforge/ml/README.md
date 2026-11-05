# ml/ — Détecteur de composants (E3 : C11, C12, C13)

| Étape | Commande | Machine conseillée |
|---|---|---|
| Préparer le dataset (fusion des sources, remappage, split sans fuite, EXIF retiré) | `uv run python microforge/ml/prepare.py --sources microforge/data/sources --out microforge/data/dataset --remplacer` | toutes |
| Valider les données (C12) | `uv run pytest microforge/tests/test_ml_data.py` | toutes |
| Entraîner (profil matériel auto) | `uv run python microforge/ml/train.py --epochs 80` | PC bureau (GPU 8 Go) / Mac M4 (`mps`) |
| Évaluer + comparer à `@production` | `uv run python microforge/ml/evaluate.py --weights runs/detect/train/weights/best.pt` | toutes |
| Enregistrer dans MLflow (alias `@staging`) | `uv run python microforge/ml/register.py --run-id <id>` | toutes |
| Chaîne complète | workflow GitHub `model-cd` (à activer : runner GPU et stockage S3 des données à mettre en place) ; `dvc repro` une fois DVC initialisé | runner GPU |

Sans GPU : notebook `colab_train.ipynb` (Google Colab / Kaggle, GPU gratuit), puis `register.py` en local.

## Entraîner sur son PC (commandes depuis la racine de PCO)

1. **Ajouter IoTKITs** (7 cartes absentes des jeux Roboflow ; licence vérifiée par le script) :
   ```bash
   uv run --with httpx python microforge/ml/fetch_mendeley.py x5thzmkxhy 1 microforge/data/raw/iotkits
   uv run python microforge/ml/coco_to_yolo.py microforge/data/raw/iotkits microforge/data/sources/iotkits
   uv run python microforge/ml/importer_zips.py --appliquer
   uv run python microforge/ml/prepare.py --sources microforge/data/sources --out microforge/data/dataset --remplacer
   ```
2. **Carte graphique** : `nvidia-smi` doit afficher la carte NVIDIA (sinon : Colab, ci-dessus). Sous
   Windows, le PyTorch de PyPI n'utilise que le processeur ; installer la version CUDA de
   l'[index officiel](https://pytorch.org/get-started/locally/), puis lancer avec `--no-sync` pour que
   uv ne remette pas la version du verrou :
   ```bash
   uv sync --all-packages --extra ml
   uv pip install --reinstall-package torch --reinstall-package torchvision torch torchvision --index-url https://download.pytorch.org/whl/cu128
   uv run --no-sync python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
   ```
3. **Entraîner** (profil choisi selon la carte détectée ; `--batch 8` si « CUDA out of memory ») :
   ```bash
   uv run --no-sync python microforge/ml/train.py --epochs 80
   ```
   `train.py` résout le chemin du dataset par rapport à `ml/data/dataset.yaml` (sinon Ultralytics le
   cherche dans son propre dossier). Résultats dans `runs/detect/<run>/` et MLflow (`mlruns/`), jamais
   commités ; la durée d'une epoch s'affiche dès la première.

## Données
Le conteneur de développement n'atteint ni Hugging Face ni Mendeley : l'inspection et le téléchargement se
font sur un runner GitHub (workflow `jeux-de-donnees`), qui publie licence, catégories et statistiques.

| Source | Statut (04/11/2026) |
|---|---|
| **IoTKITs** — Mendeley Data, DOI 10.17632/x5thzmkxhy.1 ; article *Data in Brief* (2025, PMC12149570) | **retenu** : licence CC BY 4.0 confirmée par l'API Mendeley et par l'article ; 3 200 images, 32 classes de cartes et kits, export COCO Roboflow. Une partie des images vient de Kaggle et Roboflow Universe (signalé par les auteurs) : attribution dans `ATTRIBUTION.md`. |
| Roboflow 100 « circuit-elements » (CC BY 4.0) | écarté : photos de cartes électroniques (CMS), pas de modules |
| PCB object detection (MIT) | écarté : images hébergées sur Roboflow seulement, même domaine CMS |
| **Photos personnelles** (~30 composants) | protocole : [`PHOTOS.md`](PHOTOS.md) ; servent de test réel (composants jamais vus) et d'adaptation |
| **Roboflow Universe** — 11 jeux téléchargés par Gaël (licences lues dans les README des exports) | **6 retenus**, tous CC BY 4.0 (correspondances dans `sources/*.yaml`) ; **5 écartés**, raison dans [`jeux_ecartes.yaml`](jeux_ecartes.yaml) : exports « folder » sans boîtes, détection de pièces manquantes, symboles de schéma, composants soudés sur cartes. Les 5 premiers retenus, préparés sur le PC de Gaël : 10 063 images (6 744 / 1 904 / 1 415), validation OK ; `components-model` (diodes, trimmers) ajouté ensuite. |

### Télécharger les jeux Roboflow sur le runner (sans rien télécharger soi-même)
Chaque `sources/*.yaml` d'un jeu Roboflow Universe porte son numéro de version (`roboflow_version`).
Avec une clé d'API Roboflow (compte gratuit), le workflow `jeux-de-donnees` télécharge ces jeux,
vérifie leur licence (API puis README de l'export ; refus si NC, ND ou différente de celle notée), les
fusionne avec IoTKITs puis entraîne et évalue (`fetch_roboflow.py`). Pour l'activer :

1. roboflow.com → compte gratuit → *Settings* → *API Keys* → copier la *Private API Key* ;
2. GitHub, dépôt PCO → *Settings* → *Secrets and variables* → *Actions* → *New repository secret*,
   nom `ROBOFLOW_API_KEY`. La clé ne se colle **jamais** dans une conversation ni dans un fichier.

Seule l'étape de téléchargement reçoit la clé ; elle n'apparaît dans aucun message, même d'erreur.
Ajouter un jeu = son fichier de correspondance avec `url` et `roboflow_version` (lus sur sa page Universe).

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

YOLO11n pré-entraîné, 15 epochs, 416 px, lot de 16, sur **IoTKITs seul** (8 classes de cartes) ; 31 min sur
CPU AMD EPYC 7763 (workflow `jeux-de-donnees`, run 41785539714, commit 75066c7). La validation choisit le
meilleur epoch (donc légèrement optimiste) ; le **test** n'a servi à rien pendant l'entraînement :

| Classe | Test : objets | Test mAP50 | Test mAP50-95 | Validation mAP50 | Validation mAP50-95 |
|---|---|---|---|---|---|
| **toutes** | **119** (138 images) | **0,974** | **0,930** | 0,966 | 0,930 |
| arduino_uno | 14 | 0,995 | 0,995 | 0,995 | 0,995 |
| arduino_mega | 49 | 0,995 | 0,995 | 0,995 | 0,995 |
| arduino_nano | 8 | 0,995 | 0,952 | 0,954 | 0,937 |
| arduino_due | 6 | 0,995 | 0,976 | 0,990 | 0,911 |
| arduino_micro | 3 | 0,995 | 0,940 | 0,971 | 0,945 |
| arduino_leonardo | 8 | 0,962 | 0,902 | 0,995 | 0,988 |
| esp32_devkit | 16 | 0,984 | 0,830 | 0,921 | 0,866 |
| arduino_pro_mini | 15 | 0,869 | 0,847 | 0,907 | 0,804 |

Test : précision 0,944, rappel 0,931 ; validation (273 images, 219 cartes) : précision 0,935, rappel
0,877. Inférence : 35,5 ms par image sur CPU. Les classes ayant moins de 10 objets en test (Micro, Due,
Nano, Leonardo) ont un score très instable d'un découpage à l'autre. Le run précédent (41781341808,
découpage légèrement différent) donnait en validation mAP50 0,965 et mAP50-95 0,943.

Ces chiffres valent pour des **photos de cartes seules et bien cadrées**, de même origine que
l'entraînement. **À faire** : l'entraînement sur l'ensemble des jeux (IoTKITs + jeux Roboflow, voir
ci-dessus) et la mesure sur les photos réelles de Gaël, seul test représentatif de l'usage.

Chaîne : `fetch_mendeley.py` (licence vérifiée) → `coco_to_yolo.py` → `prepare.py` (correspondance des classes
dans `sources/*.yaml`, groupes sans fuite, EXIF retiré, `manifest.json`) → `dataset_checks.py` (C12).

### Entraînement sur l'ensemble des données (04/11/2026, runner GitHub, CPU)

IoTKITs + les 6 jeux Roboflow retenus, téléchargés par le runner (`fetch_roboflow.py`, licences
vérifiées) ; YOLO11n pré-entraîné, **15 epochs**, 416 px, sur CPU Intel Xeon : 3 h 29 (workflow
`jeux-de-donnees`, run 41791374429, commit b6da7c2). Le détail par jeu (licence, images) et `stats.json`
sont dans l'artefact `iotkits-rapport` du run.

| | Images | Objets | mAP50 | mAP50-95 | Précision | Rappel |
|---|---|---|---|---|---|---|
| **Test** (jamais vu pendant l'entraînement) | 1 801 | 2 560 | **0,692** | **0,592** | 0,777 | 0,694 |
| Validation | 2 722 | 3 465 | 0,734 | 0,639 | 0,837 | 0,669 |

Inférence : 18,9 ms par image sur CPU. Par classe, sur le **test** (objets, mAP50, mAP50-95) :

| Situation | Classes |
|---|---|
| **Fiables** (≥ 30 objets, mAP50 ≥ 0,9) | `arduino_uno` (179 ; 0,995 ; 0,916), `nodemcu` (185 ; 0,995 ; 0,796), `trimmer` (192 ; 0,917 ; 0,669), `servo_sg90` (99 ; 0,982 ; 0,813), `potentiometer` (87 ; 0,990 ; 0,858), `hc_sr04` (69 ; 0,978 ; 0,873), `arduino_mega` (33 ; 0,995 ; 0,995) |
| **Correctes, à améliorer** | `push_button` (134 ; 0,895 ; 0,676), `led` (217 ; 0,844 ; 0,635), `diode` (145 ; 0,830 ; 0,644), `transistor` (228 ; 0,790 ; 0,620), `resistor` (766 ; 0,599 ; 0,424 : petits objets, nombreux par photo) |
| **En échec** | `capacitor_electrolytic` (52 ; 0,449 ; 0,189), `capacitor_ceramic` (68 ; 0,040 ; 0,012), `jumper_wires` (19 ; 0,064 ; 0,014 : moins de 30 objets, mais un score proche de zéro) |
| **Non mesurables** (moins de 30 objets en test) | `breadboard` (28 ; 0,995), `arduino_nano` (16 ; 0,991), `arduino_due` (15 ; 0,970), `arduino_leonardo` (8 ; 0,995), `screw_terminal` (7 ; 0), `arduino_micro` (6 ; 0,431), `esp32_devkit` (2 ; 0,517), `arduino_pro_mini` (2 ; 0,039), `crystal` (2 ; 0), `buzzer` (1) ; `lcd_1602` et `dc_motor` absents du test |

Lecture :
- les cartes et modules bien représentés sont reconnus de façon fiable ; les cartes IoTKITs gardent leur
  niveau en validation (Nano 0,943, Pro Mini 0,948, ESP32 0,933, Micro 0,976), mais leur test, réduit à
  quelques objets après fusion des sources, ne permet pas de conclure ;
- les condensateurs échouent : la règle « exclure » a retiré beaucoup d'images de condensateurs
  génériques, et céramiques et électrolytiques se ressemblent à 416 px ;
- 15 epochs sur CPU, c'est court pour 27 classes : le guide d'Ultralytics cité plus haut donne « environ
  300 epochs » comme point de départ courant. Prochain
  essai sur GPU (PC de Gaël ou Colab, `train.py --epochs 80`) et 640 px, avec plus de photos de
  condensateurs, fils et modules.

### Comparer les entraînements
Chaque entraînement exécuté est enregistré dans [`experiences.yaml`](experiences.yaml) (run GitHub, commit,
données, paramètres, matériel, durée, scores globaux et par classe, recopiés des journaux).
`uv run python microforge/ml/compare_runs.py` affiche le tableau de comparaison (`--split validation`,
`--json` pour une page) ; tests : `tests/test_ml_experiences.py`. Une page de comparaison avec graphiques
par classe est construite à partir de ces mêmes données (tableau de bord « Entraînements du détecteur
MicroForge »). Sur le runner, la base MLflow est temporaire : à garder en artefact au prochain
réentraînement (`mlflow.db`) pour rouvrir les runs dans l'interface MLflow.

## Licence du modèle
Ultralytics YOLO est sous **AGPL-3.0** : compatible avec un dépôt public. Alternative comparée
dans le benchmark C7 : RF-DETR (Apache 2.0, tailles N/S/M/L).
