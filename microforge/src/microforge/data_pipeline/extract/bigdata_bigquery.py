"""Source big data (option) — BigQuery, dataset public GitHub : combinaisons réelles de composants.

Toujours un **dry-run** d'abord ; plafond ``maximum_bytes_billed`` ; offre gratuite 1 To/mois.
Nécessite un projet Google Cloud et ``gcloud auth application-default login``.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from microforge.data_pipeline.base import ExtractionError, Extractor
from microforge.data_pipeline.extract.db_jlcparts import read_sql

MAX_BYTES = 60 * 1024**3


class BigQueryIncludes(Extractor):
    source = "bigquery_includes"
    kind = "bigdata"

    def setup(self) -> None:
        try:
            from google.cloud import bigquery
        except ImportError as exc:
            raise ExtractionError("google-cloud-bigquery non installé (extra bigdata)") from exc
        self.bq = bigquery
        self.client = self.params.get("client") or bigquery.Client(
            project=self.params.get("project")
        )

    def extract(self) -> list[dict[str, Any]]:
        sql = read_sql("bigquery_include_cooccurrence.sql")
        dry = self.client.query(
            sql, job_config=self.bq.QueryJobConfig(dry_run=True, use_query_cache=False)
        )
        estimated = dry.total_bytes_processed
        logger.info("BigQuery : {:.1f} Go estimés", estimated / 1024**3)
        if estimated > MAX_BYTES:
            raise ExtractionError(f"Requête trop coûteuse ({estimated / 1024**3:.0f} Go)")
        job = self.client.query(
            sql, job_config=self.bq.QueryJobConfig(maximum_bytes_billed=MAX_BYTES)
        )
        return [dict(row) for row in job.result()]
