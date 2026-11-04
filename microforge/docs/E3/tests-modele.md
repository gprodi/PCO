# Tests automatisés du modèle (C12)

| Partie | Cas testés | Outil | Fichier |
|---|---|---|---|
| Format des données | lignes YOLO (5 valeurs, classe connue, coordonnées normalisées) | pytest paramétré | `tests/test_ml_data.py` |
| Licences des sources | CC BY ou domaine public exigés (refus NC, ND, licence absente ou changée en amont : API puis README) | pytest + fausse API | `tests/test_ml_roboflow.py`, `tests/test_ml_prepare.py` |
| Archives téléchargées | chemins absolus, `..`, lettres de lecteur, liens symboliques refusés ; dossier existant jamais écrasé | pytest | `tests/test_ml_import.py`, `tests/test_ml_roboflow.py` |
| Préparation | correspondance des classes (dont « exclure »), polygones convertis en boîtes, ligne illisible = image écartée, EXIF retiré, négatives plafonnées, attribution CC BY, déterminisme | pytest | `tests/test_ml_prepare.py` |
| Découpage sans fuite | photos d'un même composant, copies augmentées et quasi-doublons (deux empreintes) dans le même split ; longue série de photos semblables placée en entraînement | pytest | idem |
| Complétude / labellisation | label manquant, image négative, classes sous-représentées | pytest | `tests/test_ml_data.py` |
| Fuites et doublons | même image (SHA-256) dans deux splits | pytest | `tests/test_ml_data.py` |
| Cohérence des classes | `dataset.yaml` = `classes.yaml` = identifiants du catalogue | pytest | `tests/test_ml_data.py` |
| Entraînement | test fumée 1 epoch CPU (`train.py --smoke`) ; entraînement réel de référence et évaluation sur le split de test (runner GitHub CPU) | CI, workflow `jeux-de-donnees` | `ml/train.py` |
| Évaluation / validation | porte de non-régression (mAP50 ≥ production − 0,02), rapport | pytest | `ml/evaluate.py` |
| Inférence | schéma de sortie, mapping classes → catalogue, affinage VLM | pytest + `StaticDetector` | `tests/test_api_ia.py` |

Couverture mesurée par `pytest --cov` (seuil 80 %).

**Versionnement des données (état au 04/11/2026).** Le dataset se reconstruit à l'identique à partir de
ce qui est versionné dans Git : chaque source est épinglée (version Roboflow `roboflow_version`, version
Mendeley et SHA-256 du zip dans `provenance.json`), sa correspondance de classes et sa licence sont dans
`ml/sources/*.yaml`, la préparation est déterministe (graine) et `manifest.json` donne l'origine, la licence
et le SHA-256 de chaque image. **DVC n'est pas encore initialisé** (seul `ml/dvc.yaml` existe) : il servira
aux photos personnelles, qui ne se retéléchargent pas, dès qu'un stockage S3 joignable depuis la CI sera
choisi (un SeaweedFS local n'est pas accessible aux runners GitHub).
```bash
uv run pytest microforge/tests/test_ml_data.py microforge/tests/test_ml_prepare.py microforge/tests/test_ml_import.py microforge/tests/test_ml_roboflow.py -q
uv run --extra ml python microforge/ml/train.py --smoke
```
