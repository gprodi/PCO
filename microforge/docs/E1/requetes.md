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
