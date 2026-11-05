# Requêtes d'extraction SQL et Spark SQL (C2)

Fichiers versionnés : `microforge/src/microforge/data_pipeline/sql/`.

| Requête | Système | Objectif | Choix (sélection, jointures, filtres) | Optimisations |
|---|---|---|---|---|
| `jlcparts_maker_parts.sql` | SQLite | composants « maker » en stock | 11 colonnes ; INNER JOIN catégories, LEFT JOIN fabricants (fabricant parfois absent) ; `stock >= :min_stock` ; motifs LIKE sur sous-catégories | index `(category_id, stock)`, filtre avant tri, `LIMIT` paramétré, colonne `extra` (JSON lourd) non lue |
| `jlcparts_best_offer.sql` | SQLite | 1 référence par MPN | `ROW_NUMBER() OVER (PARTITION BY mfr ORDER BY stock DESC)` | dédoublonnage côté SGBD (pas de transfert des doublons) |
| `spark_category_stats.sql` | Spark SQL | statistiques prix/stock par catégorie et type de montage | `get_json_object` sur le 1er palier de prix ; montage déduit du boîtier (regex) ; `HAVING >= 5` | Parquet colonnaire, pushdown du filtre `stock > 0`, `percentile_approx`, sortie partitionnée |
| `bigquery_include_cooccurrence.sql` | BigQuery | combinaisons réelles de composants | `UNNEST(REGEXP_EXTRACT_ALL(...))`, auto-jointure `a.lib < b.lib` | table échantillon, dry-run, `maximum_bytes_billed` |

## Vérification du plan d'exécution
```python
from microforge.data_pipeline.extract.db_jlcparts import JlcpartsExtractor

ex = JlcpartsExtractor(path="data/external/cache.sqlite3")
ex.setup()
print(ex.explain())
```
Avant index : `SCAN c` ; après : `SEARCH c USING INDEX idx_components_cat_stock`.

## Effet des index sur les requêtes de l'application (mesuré)
Mesure : `mf-pipeline bench-index` (module `data_pipeline/index_bench.py`), exécuté par le workflow
`collecte` sur la base PostgreSQL remplie par la collecte du jour. Pour chaque requête :
`EXPLAIN ANALYZE`, médiane de 7 passages après un passage de chauffe ; l'index existant est retiré,
ou l'index candidat créé, **dans une transaction annulée** (la base n'est jamais modifiée, ce que
vérifie `tests/test_index_bench.py`). Paramètres tirés des données : composant et référence
fabricant situés au milieu de l'ordre des clés, catégorie de ce composant.

Run `collecte` n° 6 (05/11/2026, runner GitHub `ubuntu-latest`, PostgreSQL 17.11) : 99 325
composants, 106 819 offres, 13 catégories.

| Requête | Usage | Index | Sans index | Avec index | Gain |
|---|---|---|---|---|---:|
| offres d'un composant | `GET /v1/components/{id}/offers` | `ix_offre_component_id` | 7,447 ms (lecture complète d'`offre`) | 0,032 ms | ×233 |
| composant par référence | rapprochement d'une offre (MPN) | `ix_composant_mpn` | 12,761 ms (lecture complète de `composant`) | 0,017 ms | ×751 |
| liste d'une catégorie (50 lignes, triées) | `GET /v1/components?category=` | `ix_composant_category_id` (index simple, ancien) | 2,275 ms (parcours de la clé primaire) | 3,718 ms (toute la catégorie lue puis triée) | ×0,6 |
| liste d'une catégorie (50 lignes, triées) | idem | `(category_id, id)` (candidat) | 3,689 ms | 0,034 ms (une lecture ordonnée) | ×108 |
| recherche « contient » dans le nom | `?q=` limité au nom | trigrammes `pg_trgm` sur `name` (candidat) | 118,690 ms | 0,030 ms | ×3 956 |

Décisions :
- l'index simple sur la catégorie **ralentissait** la liste par catégorie : il est remplacé par
  l'index composite `(category_id, id)`, qui sert le filtre et le tri (migration Alembic `0003`) ;
- les trigrammes divisent par près de 4 000 la recherche sur le nom ; la route actuelle cherche aussi
  dans l'identifiant et la description (`OR`) : sa mesure telle quelle, avec trois index trigrammes
  candidats, est ajoutée au banc avant toute migration.
