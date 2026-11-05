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

Décisions, puis vérification au run `collecte` n° 7 (même jour, mêmes volumes, après la migration `0003`) :

| Requête | Index | Sans index | Avec index | Gain |
|---|---|---|---|---:|
| liste d'une catégorie (50 lignes, triées) | `ix_composant_category_id_id` (en place) | 3,313 ms | 0,040 ms | ×83 |
| recherche de la route telle quelle (`name`, `id` ou `description` `ILIKE '%…%'`) | trois index trigrammes (candidats) | 104,911 ms (lecture complète) | 0,044 ms (trois lectures d'index combinées) | ×2 384 |
| recherche « contient » dans le nom seul | trigrammes sur `name` (candidat) | 95,100 ms | 0,023 ms | ×4 135 |

- l'index simple sur la catégorie **ralentissait** la liste par catégorie : remplacé par l'index composite
  `(category_id, id)`, qui sert le filtre et le tri (migration Alembic `0003`) ;
- la route de recherche, mesurée telle quelle, passe de 105 ms à 0,04 ms avec un index trigrammes sur
  chacune de ses trois colonnes : index ajoutés (migration `0004`, PostgreSQL seulement ; sous SQLite,
  en développement, la recherche reste une lecture complète). Coût : trois index GIN à tenir à jour
  pendant l'import hebdomadaire, acceptable pour un catalogue surtout lu.

Le banc mesure désormais ces index comme « existants » (retirés dans une transaction annulée).

### Statistiques du planificateur après l'import (run `collecte` n° 8)
Au run 8, les index (composite et trigrammes) existaient déjà avant l'import : ils sont créés avec la
table. Mesurés juste après le chargement, sans statistiques à jour, ils donnaient de moins bons plans :
liste d'une catégorie 3,810 ms (lecture bitmap puis tri, au lieu de 0,040 ms), recherche de la route
2,635 ms (au lieu de 0,044 ms). Cause : après un chargement massif, PostgreSQL garde les statistiques
de tables vides jusqu'au passage de l'autovacuum. Premier correctif : `ANALYZE` des tables chargées à la
fin de chaque import.

Run `collecte` n° 9 (avec cet `ANALYZE`) : la liste d'une catégorie revient à 0,064 ms (×36), mais la
recherche reste à 5,258 ms (route complète) et 1,955 ms (nom seul), loin des 0,04 ms mesurés quand les
mêmes index étaient construits après les données. Cause, vérifiée sur une base PostgreSQL : les lignes
insérées dans un index GIN vont d'abord dans une **liste en attente**, lue séquentiellement à chaque
recherche ; seuls `VACUUM`, l'autovacuum ou `gin_clean_pending_list` l'intègrent à l'index, pas un
`ANALYZE` manuel. Après un import par lots de 99 000 lignes : 233, 154 et 233 pages en attente,
recherche 5,308 ms ; après `gin_clean_pending_list` : 0 page, 0,094 ms. Correctif : la fin de l'import
(`load/importer.py`, `refresh_after_load`) intègre les listes en attente des index GIN puis lance
`ANALYZE` ; un test sur PostgreSQL vérifie les statistiques et l'absence de pages en attente.

### État final après import (run `collecte` n° 10)
Avec ce correctif, tous les index sont en place dès l'import (aucun n'est plus « candidat ») et la base
répond vite sans intervention :

| Requête | Index | Sans index | Avec index | Gain |
|---|---|---|---|---:|
| offres d'un composant | `ix_offre_component_id` | 5,255 ms | 0,020 ms | ×263 |
| composant par référence fabricant | `ix_composant_mpn` | 8,387 ms | 0,012 ms | ×699 |
| liste d'une catégorie (50 lignes, triées) | `ix_composant_category_id_id` | 1,537 ms | 0,031 ms | ×50 |
| recherche « contient » dans le nom | `ix_composant_name_trgm` | 95,210 ms | 0,023 ms | ×4 140 |
| recherche de l'API (nom, identifiant ou description) | trois index trigrammes | 104,602 ms | 0,043 ms | ×2 433 |

Durée de l'étape « collecte, agrégation, import » : 95 s aux runs 6 et 7, 118 s au run 8, 100 s au
run 10 (index GIN tenus à jour puis listes en attente intégrées). L'écart comprend aussi le
téléchargement des sources : il n'isole pas le coût des index.

