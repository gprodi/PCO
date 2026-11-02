-- C2 — Meilleure référence LCSC par numéro de pièce fabricant (dédoublonnage côté SGBD).
--
-- Une même MPN peut exister sous plusieurs références LCSC (conditionnements différents).
-- La fonction fenêtre ROW_NUMBER() garde celle qui a le plus de stock (à égalité : la plus ancienne
-- référence). Évite de rapatrier puis trier tous les doublons côté Python.
SELECT lcsc, mpn, stock, price_json
FROM (
    SELECT
        c.lcsc,
        c.mfr   AS mpn,
        c.stock,
        c.price AS price_json,
        ROW_NUMBER() OVER (PARTITION BY c.mfr ORDER BY c.stock DESC, c.lcsc ASC) AS rang
    FROM components AS c
    WHERE c.mfr IS NOT NULL AND c.mfr <> ''
)
WHERE rang = 1;
