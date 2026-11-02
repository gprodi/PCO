# Monitoring du modèle (C11)

| Métrique | Signification | Collecte | Seuil / déclencheur |
|---|---|---|---|
| `mf_detection_correction_rate{source}` | part des détections corrigées par les utilisateurs (7 j) | table `retour_detection` → `/metrics` d'api_data | > 25 % pendant 1 h → **réentraînement** (`repository_dispatch: retrain`) |
| `mf_detection_confidence` (histogramme) | confiance des prédictions | api_ia | moyenne < 0,5 sur 24 h → enquête dérive |
| `mf_detections_unknown_total` | objets hors catalogue | api_ia | > 20 % sur 6 h → enrichir catalogue/dataset |
| `mf_scan_seconds` | durée d'analyse | api_ia | p95 > 5 s → vérifier profil/modèle |
| mAP50 (lot de retours étiquetés) | performance réelle | job hebdomadaire `evaluate.py` | baisse > 5 points → réentraînement |

**Restitution** : tableau Grafana « MicroForge — Modèle de vision » (titres explicites, seuils écrits dans
les titres, palette lisible par les daltoniens, valeurs en légende tabulaire) ; alertes Discord.

**Bac à sable** : `traffic_generator.py --drift` injecte des photos sombres et 60 % de corrections →
l'alerte `TauxCorrectionsEleve` doit passer à l'état *firing* (capture à joindre au rapport).
