# Résolution d'incidents (C21)

Procédure : issue « Incident » (`.github/ISSUE_TEMPLATE/incident.md`) → reproduction en développement →
débogage documenté dans l'issue → correctif par PR liée → post-mortem ci-dessous.

## Incident n°1 — Câblage généré invalide pour une entrée analogique sur ESP32 avec Wi-Fi
- **Symptôme** : lectures analogiques bloquées à 4095 dès que le Wi-Fi est activé.
- **Cause** : broche ADC2 affectée alors que le Wi-Fi utilise l'ADC2.
- **Correctif** : règle de l'allocateur « ADC1 uniquement si `uses_wifi` » + test `test_esp32_wifi_forces_adc1`.
- **Prévention** : test par propriétés (hypothesis) sur l'allocateur.

## Incident n°2 — (à documenter) …
| Étape | Contenu |
|---|---|
| Message d'erreur / logs | |
| Reproduction | |
| Recherche (docs, forums) | |
| Cause | |
| Solution + PR | |
