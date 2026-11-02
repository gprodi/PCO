"""Source big data — Apache Spark (PySpark, Spark SQL) sur le dump LCSC complet.

Étapes :
1. ``export_parquet`` : jlcparts SQLite -> Parquet partitionné (lecture par lots, mémoire bornée) ;
2. ``run_spark`` : session Spark locale (mémoire selon le profil matériel), vue ``components``,
   exécution de ``sql/spark_category_stats.sql``, écriture Parquet partitionnée par catégorie.

Installer l'extra ``bigdata`` (pyspark) et Java 17+. Sur le PC du bureau (128 Go de RAM) :
``mf-pipeline spark --driver-memory 16g``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from loguru import logger

from microforge.data_pipeline.base import ExtractionError, Extractor
from microforge.data_pipeline.extract.db_jlcparts import read_sql

EXPORT_QUERY = """
SELECT c.lcsc, c.mfr AS mpn, cat.category, cat.subcategory, c.package, c.stock, c.price AS price_json
FROM components c JOIN categories cat ON cat.id = c.category_id
"""


def export_parquet(sqlite_path: Path, out_dir: Path, batch_size: int = 200_000) -> int:
    """Exporte la base SQLite en fichiers Parquet (un par lot) ; renvoie le nombre de lignes."""
    import polars as pl

    out_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    total = 0
    try:
        cursor = conn.execute(EXPORT_QUERY)
        cols = [d[0] for d in cursor.description]
        part = 0
        while rows := cursor.fetchmany(batch_size):
            pl.DataFrame(rows, schema=cols, orient="row").write_parquet(
                out_dir / f"part-{part:05d}.parquet"
            )
            total += len(rows)
            part += 1
    finally:
        conn.close()
    logger.info("Export Parquet : {} lignes -> {}", total, out_dir)
    return total


class SparkCategoryStats(Extractor):
    source = "spark_lcsc"
    kind = "bigdata"

    def setup(self) -> None:
        try:
            from pyspark.sql import SparkSession
        except ImportError as exc:
            raise ExtractionError("pyspark non installé (uv sync --extra bigdata)") from exc
        self.spark = (
            SparkSession.builder.appName("microforge-lcsc")
            .master(self.params.get("master", "local[*]"))
            .config("spark.driver.memory", self.params.get("driver_memory", "4g"))
            .config("spark.sql.shuffle.partitions", self.params.get("shuffle_partitions", "64"))
            .getOrCreate()
        )

    def teardown(self) -> None:
        if getattr(self, "spark", None):
            self.spark.stop()

    def extract(self) -> list[dict[str, Any]]:
        parquet = Path(self.params.get("parquet_dir", "data/interim/lcsc_parquet"))
        if not parquet.exists():
            raise ExtractionError(
                f"Parquet introuvable : {parquet} (lancer d'abord export_parquet)"
            )
        df = self.spark.read.parquet(str(parquet))
        df.createOrReplaceTempView("components")
        stats = self.spark.sql(read_sql("spark_category_stats.sql"))
        out = Path(self.params.get("out_dir", "data/interim/lcsc_stats"))
        stats.write.mode("overwrite").partitionBy("montage").parquet(str(out))
        return [row.asDict() for row in stats.limit(int(self.params.get("sample", 200))).collect()]
