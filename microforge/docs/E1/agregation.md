# Agrégation et nettoyage (C3)

Code : `data_pipeline/aggregate/` — commande `uv run mf-pipeline aggregate`.

## Enchaînement
1. Union des enregistrements bruts (format commun `RawPart`) de toutes les sources.
2. Nettoyage des textes (HTML, entités, espaces, Unicode NFKC).
3. Normalisation des formats (tableau ci-dessous).
4. Détection et suppression des entrées corrompues (règles R1 à R5), comptées dans `rejects_report.json`.
5. Rapprochement avec le catalogue (alias, puis similarité rapidfuzz ≥ 88).
6. Dédoublonnage des offres (fournisseur, référence) en gardant la plus récente.
7. Sorties Parquet : `components_clean`, `offers_clean`.

## Homogénéisation
| Donnée | Exemples en entrée | Sortie |
|---|---|---|
| Tension | « 3V3 », « 3,3 V », « 2.7V ~ 5.5V », « 1800mV » | `(min, max)` en volts |
| Prix | « 3,50 € », « 1.234,50 », USD/CNY | float EUR au taux BCE du jour |
| Stock | « 1 234 En stock », « Rupture » | entier |
| MPN | « am2302-tr » | `AM2302` |
| Fabricant | « ESPRESSIF SYSTEMS (SHANGHAI) CO., LTD. » | `Espressif` |
| Boîtier | « DIP8 », « Plugin » | `DIP-8`, `MODULE` |
| Interfaces | « I²C / IIC, analog » | `I2C,ADC` |
| Dates | « 30/10/2026 », ISO avec fuseau | ISO 8601 UTC |

## Règles de rejet
| Règle | Condition | Traitement |
|---|---|---|
| R1 identite_manquante | ni MPN ni nom | supprimée |
| R2 prix_invalide | prix absent, nul ou négatif | offre supprimée |
| R3 devise_inconnue | devise sans taux | offre supprimée |
| R4 stock_negatif | stock < 0 | supprimée |
| R5 prix_aberrant | hors [Q1 − 3·IQR ; Q3 + 3·IQR] par catégorie (≥ 8 offres) | offre supprimée |

Tests : `microforge/tests/test_pipeline.py` (règles unitaires + agrégation de bout en bout).
