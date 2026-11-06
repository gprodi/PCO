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


## Incident n°10 — La supervision ne démarrait pas et ses alertes ne partaient nulle part (06/11/2026)
| Étape | Contenu |
|---|---|
| Message d'erreur / logs | premier lancement réel du profil `monitoring` : Grafana s'arrête au démarrage, `failure to map file contact-points.yml: failure parsing contact points: discord-microforge: could not find webhook url property in settings` ; `curl localhost:3000/api/health` ne répond pas |
| Analyse | le point de contact Discord était provisionné dans Grafana avec `${DISCORD_WEBHOOK_URL}`, vide par défaut : Grafana refuse un point de contact sans adresse. En lisant la chaîne, deuxième défaut : les règles d'alerte vivent dans Prometheus, mais aucun Alertmanager n'existait, donc aucune alerte n'était envoyée. L'essai avec du trafic réel en a révélé trois autres : latence p95 lue sur un histogramme plafonné à 1 s (seuil de 2 s inatteignable), compteurs de détection créés à la première photo (confiance moyenne `NaN`), part d'objets inconnus divisée par les seules détections reconnues (alerte muette quand tout est inconnu) |
| Reproduction | `docker compose --profile monitoring up -d` sans `DISCORD_WEBHOOK_URL` ; `traffic_generator.py --drift` ; requêtes PromQL des règles sur `/api/v1/query` |
| Solution | service `alertmanager` (Discord seulement si l'adresse est fournie, `start.sh`) relié à Prometheus et à Loki ; point de contact retiré de Grafana ; histogramme fin pour la latence ; séries de détection créées à 0 au démarrage ; dénominateur = toutes les détections ; règle Loki pour les échecs de connexion, jusque-là documentée sans exister |
| Prévention | `promtool test rules` sur `alerts.test.yml` (les tests échouent sur les anciennes règles), `tests/test_monitoring.py`, job CI « Supervision » qui démarre la pile et vérifie Grafana, Alertmanager et Loki |

## Incident n°11 — Analyse de photo refusée (401) après un redémarrage d'api_data (06/11/2026)
| Étape | Contenu |
|---|---|
| Message d'erreur / logs | pendant l'essai de supervision, `traffic_generator.py` affiche `scan 401` pour chaque photo ; api_data accepte la connexion (`POST /v1/auth/token -> 200`), api_ia refuse le jeton (`Jeton invalide`) |
| Analyse | sans clés JWT configurées (cas par défaut de `.env.example`, `MF_ENV=dev`), api_data génère une paire de clés éphémère à chaque démarrage. api_ia lit la clé publique une fois et la garde en cache : après `docker compose restart api_data`, tous les jetons neufs étaient refusés jusqu'au redémarrage d'api_ia. Chez un utilisateur : photo, génération et copilote en échec, sans cause visible |
| Reproduction | lancer les deux API, redémarrer api_data seule, se reconnecter puis analyser une photo |
| Solution | `api_ia/deps.py` : sur une signature invalide, la clé publique d'api_data est relue une fois (au plus toutes les 30 s), seulement quand elle ne vient pas de l'environnement ; un jeton signé par une autre clé reste refusé |
| Prévention | `test_cle_publique_relue_apres_redemarrage_d_api_data` (clé changée : accepté après relecture ; jeton étranger : refusé, sans relecture en boucle) ; vérifié sur les API réelles (journal « relecture de la clé publique », photos acceptées) |
