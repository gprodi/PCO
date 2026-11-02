-- C2 (big data, option) — Quels composants les makers utilisent-ils ENSEMBLE ?
-- Co-occurrence des #include dans les sketches Arduino (.ino) de l'échantillon public GitHub.
--
-- Coût : TOUJOURS lancer d'abord en dry-run (octets estimés) ; plafond maximum_bytes_billed.
-- La table `sample_contents` (échantillon) suffit et reste dans l'offre gratuite (1 To/mois).
WITH includes AS (
    SELECT DISTINCT id, LOWER(inc) AS lib
    FROM `bigquery-public-data.github_repos.sample_contents`,
         UNNEST(REGEXP_EXTRACT_ALL(content, r'#include\s*[<"]([^>"]+)[>"]')) AS inc
    WHERE sample_path LIKE '%.ino'
)
SELECT a.lib AS lib_a, b.lib AS lib_b, COUNT(DISTINCT a.id) AS sketches
FROM includes AS a
JOIN includes AS b ON a.id = b.id AND a.lib < b.lib
WHERE a.lib NOT IN ('arduino.h', 'wire.h', 'spi.h')
  AND b.lib NOT IN ('arduino.h', 'wire.h', 'spi.h')
GROUP BY lib_a, lib_b
HAVING sketches >= 3
ORDER BY sketches DESC
LIMIT 200
