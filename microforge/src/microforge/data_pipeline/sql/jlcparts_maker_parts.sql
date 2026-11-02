-- C2 — Extraction des composants « maker » du catalogue LCSC (base SQLite jlcparts).
--
-- Objectif   : capteurs, afficheurs, modules, MCU et drivers DISPONIBLES (stock suffisant),
--              avec leur fabricant, catégorie et grille de prix (JSON) pour le C3.
-- Sélection  : projection limitée aux 11 colonnes utiles (la colonne `extra` JSON, volumineuse,
--              n'est pas lue).
-- Jointures  : `categories` (INNER : toute pièce a une catégorie) ; `manufacturers` en LEFT JOIN
--              (le fabricant peut manquer -> entrée conservée puis signalée par le C3).
-- Filtrage   : stock minimal paramétré (:min_stock) appliqué AVANT le tri ; motifs LIKE sur
--              la sous-catégorie (vocabulaire LCSC en anglais).
-- Optimisations :
--   * index conseillé : CREATE INDEX IF NOT EXISTS idx_components_cat_stock
--                       ON components(category_id, stock);
--     (vérifié avec EXPLAIN QUERY PLAN : « SEARCH c USING INDEX idx_components_cat_stock »)
--   * LIMIT paramétré (:max_rows) pour borner le volume transféré.
SELECT
    c.lcsc           AS lcsc,
    c.mfr            AS mpn,
    m.name           AS manufacturer,
    cat.category     AS category,
    cat.subcategory  AS subcategory,
    c.package        AS package,
    c.description    AS description,
    c.datasheet      AS datasheet_url,
    c.stock          AS stock,
    c.price          AS price_json,
    c.basic          AS is_basic
FROM components AS c
JOIN categories AS cat ON cat.id = c.category_id
LEFT JOIN manufacturers AS m ON m.id = c.manufacturer_id
WHERE c.stock >= :min_stock
  AND (
        cat.subcategory LIKE '%Sensor%'
     OR cat.subcategory LIKE '%Display%'
     OR cat.subcategory LIKE '%OLED%'
     OR cat.subcategory LIKE '%Microcontroller%'
     OR cat.subcategory LIKE '%Motor Driver%'
     OR cat.subcategory LIKE '%Real-time Clock%'
     OR cat.subcategory LIKE '%Buzzer%'
     OR cat.subcategory LIKE '%LED%'
     OR cat.category    LIKE '%Development Boards%'
  )
ORDER BY c.stock DESC
LIMIT :max_rows;
