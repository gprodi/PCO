"""Orchestration Prefect (cours MLOPS 3) : collecte parallèle -> agrégation -> import -> purge.

Si Prefect n'est pas installé, les décorateurs deviennent neutres : le flow s'exécute en Python
pur (utile en CI et sur le PC de l'école).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

try:  # pragma: no cover - dépend de l'environnement
    from prefect import flow, task
except ImportError:  # pragma: no cover

    def task(fn=None, **_kw):  # type: ignore[no-redef]
        return fn if fn else (lambda f: f)

    def flow(fn=None, **_kw):  # type: ignore[no-redef]
        return fn if fn else (lambda f: f)


from microforge.data_pipeline.aggregate.aggregate import Aggregator, load_raw, write_outputs
from microforge.data_pipeline.extract import EXTRACTORS


@task(retries=2, retry_delay_seconds=30)
def extract_task(source: str, raw_dir: Path, params: dict[str, Any]) -> dict[str, Any]:
    _, manifest = EXTRACTORS[source](out_dir=raw_dir, **params).run()
    return {"source": source, "status": manifest.status, "rows": manifest.rows}


@task
def aggregate_task(raw_dir: Path, out_dir: Path) -> dict[str, Any]:
    records, fx = load_raw(raw_dir)
    components, offers, report = Aggregator(fx).run(records)
    write_outputs(components, offers, report, out_dir)
    return report.to_dict()


@flow(name="microforge-collecte")
def collect_flow(
    sources: dict[str, dict[str, Any]] | None = None,
    raw_dir: str = "data/raw",
    out_dir: str = "data/clean",
) -> dict[str, Any]:
    """Flow complet. ``sources`` = {nom: paramètres} ; par défaut les sources sans clé d'API."""
    sources = sources or {"fx": {}, "arduino_index": {}}
    raw, out = Path(raw_dir), Path(out_dir)
    results = [extract_task(name, raw, params) for name, params in sources.items()]
    failed = [r for r in results if r["status"] != "success"]
    if failed:
        logger.warning("Sources en échec : {}", failed)
    report = aggregate_task(raw, out)
    return {"extractions": results, "aggregation": report}
