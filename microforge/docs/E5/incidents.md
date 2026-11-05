# Résolution d'incidents (C21)

Procédure : issue « Incident » (`.github/ISSUE_TEMPLATE/incident.md`) → reproduction en développement →
débogage documenté dans l'issue → correctif par PR liée → post-mortem ci-dessous.

## Règle de conception — Câblage généré invalide pour une entrée analogique sur ESP32 avec Wi-Fi
- **Symptôme** : lectures analogiques bloquées à 4095 dès que le Wi-Fi est activé.
- **Cause** : broche ADC2 affectée alors que le Wi-Fi utilise l'ADC2.
- **Correctif** : règle de l'allocateur « ADC1 uniquement si `uses_wifi` » + test `test_esp32_wifi_forces_adc1`.
- **Prévention** : test par propriétés (hypothesis) sur l'allocateur.

## Incidents n° 1 à 4 (02/11/2026)
Résumés dans le rapport E5 : CI rouge (extras uv non installés, dossier d'installation d'arduino-cli
absent), page « Explorer » en erreur (méthodes absentes du client, SVG passé en octets à Pillow), faux
échecs de compilation (mauvais dossier de sketch), projets SPI non compilables sur AVR (constante
`PIN_SPI_MOSI` déjà définie comme macro par le cœur Arduino).

## Incident n°5 — Score de test introuvable après un entraînement « réussi » (03-04/11/2026)
| Étape | Contenu |
|---|---|
| Message d'erreur / logs | Run `jeux-de-donnees` 41781341808 vert, mais aucun score sur le split de test ; les poids `best.pt` étaient rangés sous `.venv/lib/python3.12/site-packages/tests/tmp/runs/detect/runs/detect/<id>/` |
| Reproduction | relecture du journal de l'entraînement : `save_dir` pointe dans le paquet installé, pas dans le dépôt |
| Recherche | réglages d'Ultralytics (`yolo settings`) : un `project` relatif est préfixé par `runs_dir` ; Bash : le code de sortie d'un tube est celui de la dernière commande (`tee`) sauf avec `set -o pipefail` |
| Cause | chemin de résultats relatif + échec de l'évaluation masqué par `\| tee` |
| Solution | commit 75066c7 : `--project` résolu en chemin absolu dans `ml/train.py`, `set -o pipefail`, `test -n "$best"` ; run 41785539714 : premier score de test (mAP50 0,974) |
| Prévention | toute étape de CI avec un tube utilise `pipefail` ; le chemin des poids est vérifié avant l'évaluation |

## Incident n°6 — Faux positif de détection de secret (04/11/2026)
| Étape | Contenu |
|---|---|
| Message d'erreur / logs | job « Détection de secrets (gitleaks) » rouge : règle `generic-api-key`, `revision/boilerplates/fastapi-jwt-sqlmodel/.env.example`, ligne 2 |
| Analyse | la valeur signalée était un texte d'exemple (« remplacer-par-une-valeur-aleatoire… »), pas un secret ; vérifié à la main dans le diff |
| Recherche | documentation gitleaks : un constat accepté s'ignore par son empreinte dans `.gitleaksignore` (le commit reste dans l'historique de la PR) |
| Solution | commit 7f84218 : valeur vidée, l'API refuse de démarrer sans clé de 32 caractères, empreinte ajoutée à `.gitleaksignore` |
| Prévention | les `.env.example` ne contiennent jamais de valeur, même factice |

## Incident n°7 — Annotations en polygones ignorées sans avertissement (04/11/2026)
| Étape | Contenu |
|---|---|
| Message d'erreur / logs | aucun message : `stats.json` montrait 0 objet pour le jeu « kit Arduino » (LCD, moteur, buzzer, fils Dupont absents) |
| Analyse | les fichiers de labels de ce jeu ont plus de 5 valeurs par ligne : format « segmentation » YOLO (polygones), que `prepare.py` sautait ; les images restaient comme images sans objet, ce qui apprend au modèle que ces composants sont du décor |
| Recherche | format des labels Ultralytics (détection : `classe cx cy w h` ; segmentation : `classe x1 y1 x2 y2 …`) |
| Solution | commit b1510c2 : polygone converti en boîte englobante, ligne illisible = image écartée et comptée (`images_labels_illisibles`), `polygones_convertis` dans `stats.json` ; 2 513 objets récupérés (airost 922, cv2024 872, kit Arduino 719) |
| Prévention | tests `test_label_lines_boxes_polygons_and_garbage` et `test_polygon_labels_are_converted_and_unreadable_images_dropped` ; plus aucune ligne ignorée sans être comptée |

## Incident n°8 — Test rouge sous Python 3.12 seulement (04/11/2026)
| Étape | Contenu |
|---|---|
| Message d'erreur / logs | CI run 88 (b6da7c2), job « Python 3.12 » : `FAILED microforge/tests/test_ml_import.py::test_zip_is_extracted_and_described - assert ("images : 4 {'train': 3, 'valid': 1}" in '# Jeux de photos importés…')` ; le job Python 3.13 du même commit est vert |
| Analyse | même code, résultat différent selon la version : le rapport dépend d'un ordre non garanti. `describe()` compte les images par split dans l'ordre renvoyé par `Path.rglob`, qui diffère entre 3.12 et 3.13 |
| Reproduction | Python 3.12 absent du poste : un test inverse l'ordre de `rglob` ; il échoue sur l'ancien code (`1 failed, 10 passed`) et passe avec le correctif (`11 passed`) |
| Solution | commit 69e0366 : images triées (`sorted(...)`) avant le décompte |
| Prévention | test `test_report_does_not_depend_on_filesystem_order` ; matrice CI 3.12 + 3.13 conservée, c'est elle qui a révélé le défaut |

## Incident n°9 — Génération du DDL hors ligne cassée depuis la migration 0002 (05/11/2026)
| Étape | Contenu |
|---|---|
| Message d'erreur / logs | `MF_DATABASE_URL=postgresql://u@h/microforge uv run alembic upgrade head --sql` (commande citée par le dossier E1 pour produire le MPD) s'arrête après la révision 0001 : `sqlalchemy.exc.NoInspectionAvailable: No inspection system is available for object of type <class 'sqlalchemy.engine.mock.MockConnection'>`, code de sortie 1 |
| Analyse | en mode hors ligne, Alembic écrit le SQL sans base : la connexion est factice. La migration 0002 (03/11) lit le nom de l'ancienne contrainte d'unicité en inspectant la base ; c'est impossible hors ligne. Aucun test ne couvrait ce mode : la commande documentée était cassée depuis deux jours sans que rien ne le signale |
| Reproduction | la commande exacte du dossier E1 ; trouvé en vérifiant le SQL hors ligne de la nouvelle migration 0004 |
| Solution | hors ligne, 0002 utilise le nom que PostgreSQL donne à une contrainte sans nom (`article_inventaire_user_id_component_id_location_key`, relevé sur une base réelle après `alembic upgrade 0001`) ; `migrations/env.py` lit l'URL de la configuration aussi hors ligne |
| Prévention | test `test_offline_sql_for_postgresql_needs_no_database` : DDL PostgreSQL complet sans base (15 `CREATE TABLE`, la suppression de l'ancienne contrainte, les index composites et trigrammes) |

