"""Gros volume avec Spark : même filtrage que la version Polars, sur une grappe ou en local.

En local : ``depuis_gros_volume(..., moteur="spark")``. Sur une grappe :
``spark-submit collecte/spark_job.py "donnees/*.csv" sortie/`` (lignes JSON).
"""

import sys
from collections.abc import Iterable
from typing import Any


def session_locale(nom: str = "collecte"):
    from pyspark.sql import SparkSession

    return (
        SparkSession.builder.master("local[2]")
        .appName(nom)
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )


def _filtrer(spark, motif: str, colonnes: dict[str, str], genres: Iterable[str], colonne_genre: str):
    from pyspark.sql import functions as F

    table = spark.read.option("header", True).csv(motif)
    motif_genre = "|".join(g.lower() for g in genres)
    table = table.filter(F.lower(F.col(colonne_genre)).rlike(motif_genre))
    table = table.select([F.col(col).alias(cible) for cible, col in colonnes.items()])
    if {"titre", "annee"} <= set(colonnes):
        table = table.dropDuplicates(["titre", "annee"])
    return table


def agreger(
    spark, motif: str, colonnes: dict[str, str], genres: Iterable[str], colonne_genre: str = "genres"
) -> list[dict[str, Any]]:
    return [ligne.asDict() for ligne in _filtrer(spark, motif, colonnes, genres, colonne_genre).collect()]


def main(argv: list[str]) -> None:  # pragma: no cover - lancé par spark-submit
    motif, sortie = argv[1], argv[2]
    spark = session_locale()
    colonnes = {"titre": "primaryTitle", "annee": "startYear", "genre": "genres", "note": "averageRating"}
    _filtrer(spark, motif, colonnes, ["horror"], "genres").write.mode("overwrite").json(sortie)
    spark.stop()


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv)
