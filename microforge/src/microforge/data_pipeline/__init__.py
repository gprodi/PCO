"""Pipeline de données E1 (C1–C5) : collecte multi-sources -> agrégation -> base -> API.

Sources (les 5 types exigés par le critère C1) :

=================  ==========================================  =============================
Type               Cible                                       Module
=================  ==========================================  =============================
Service web REST   DigiKey v4, Mouser, GitHub, Frankfurter     ``extract/rest_*.py``
Fichier            library_index.json Arduino, pièces Fritzing ``extract/file_*.py``
Scraping           boutique française (config ``shops.yaml``)  ``extract/scrape_shop.py``
Base de données    jlcparts ``cache.sqlite3`` (catalogue LCSC) ``extract/db_jlcparts.py``
Big data           Spark SQL sur le dump LCSC complet          ``extract/bigdata_spark.py``
                   (option : BigQuery, dataset GitHub)         ``extract/bigdata_bigquery.py``
=================  ==========================================  =============================
"""
