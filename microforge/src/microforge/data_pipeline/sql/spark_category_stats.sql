-- C2 (big data) — Statistiques par catégorie sur le dump LCSC COMPLET (Spark SQL).
-- Vue `components` = Parquet exporté de jlcparts (plusieurs millions de lignes).
--
-- * get_json_object : premier palier de prix dans la colonne JSON (évite un from_json coûteux) ;
-- * montage déduit du boîtier par expression régulière (traversant/module = adapté aux makers) ;
-- * percentile_approx : médiane approximative distribuée (un tri global serait trop coûteux) ;
-- * HAVING : écarte les catégories marginales (< 5 références).
-- Optimisations : lecture Parquet colonnaire (seules 5 colonnes lues), filtre `stock > 0`
-- poussé au scan (predicate pushdown), partitionnement de sortie par catégorie.
WITH prix AS (
    SELECT
        category,
        subcategory,
        stock,
        CAST(get_json_object(price_json, '$[0].price') AS DOUBLE) AS unit_price_usd,
        CASE
            WHEN package RLIKE '(?i)(DIP|TO-92|TO-220|THT|Plugin|Module|Through Hole)' THEN 'traversant_module'
            ELSE 'cms'
        END AS montage
    FROM components
    WHERE stock > 0
)
SELECT
    category,
    subcategory,
    montage,
    COUNT(*)                                AS nb_references,
    SUM(stock)                              AS stock_total,
    percentile_approx(unit_price_usd, 0.5)  AS prix_median_usd,
    MIN(unit_price_usd)                     AS prix_min_usd
FROM prix
WHERE unit_price_usd IS NOT NULL AND unit_price_usd > 0
GROUP BY category, subcategory, montage
HAVING COUNT(*) >= 5
ORDER BY nb_references DESC
