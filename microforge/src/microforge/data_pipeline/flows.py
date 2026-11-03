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


from microforge.data_pipeline.aggregate.aggregate import (
    Aggregator,
    load_libraries,
    load_raw,
    write_outputs,
)
from microforge.data_pipeline.extract import EXTRACTORS

#: Sources sans clé d'API (les extracteurs DigiKey/Mouser s'ajoutent avec leurs clés).
DEFAULT_SOURCES: dict[str, dict[str, Any]] = {
    "fx": {},
    "arduino_index": {},
    "lcsc": {},
    "github": {},
}


@task(retries=2, retry_delay_seconds=30)
def extract_task(source: str, raw_dir: Path, params: dict[str, Any]) -> dict[str, Any]:
    _, manifest = EXTRACTORS[source](out_dir=raw_dir, **params).run()
    return {
        "source": source,
        "status": manifest.status,
        "rows": manifest.rows,
        "duration_s": manifest.duration_s,
        "message": manifest.message,
    }


@task
def aggregate_task(raw_dir: Path, out_dir: Path) -> dict[str, Any]:
    records, fx = load_raw(raw_dir)
    components, offers, report = Aggregator(fx).run(records)
    write_outputs(components, offers, report, out_dir, load_libraries(raw_dir))
    return report.to_dict()


@task
def load_task(out_dir: Path) -> dict[str, Any]:
    """Import du jeu nettoyé dans la base désignée par ``MF_DATABASE_URL`` (C4)."""
    from sqlmodel import Session

    from microforge.api_data.db import get_engine, init_db
    from microforge.data_pipeline.load.importer import import_clean, read_clean

    init_db()
    comps, offers, libs = read_clean(out_dir)
    with Session(get_engine()) as session:
        run = import_clean(session, comps, offers, libs)
        return {"status": run.status, "rows_out": run.rows_out, "run_id": run.id}


@flow(name="microforge-collecte")
def collect_flow(
    sources: dict[str, dict[str, Any]] | None = None,
    raw_dir: str = "data/raw",
    out_dir: str = "data/clean",
    load_db: bool = True,
) -> dict[str, Any]:
    """Collecte (sources indépendantes : un échec n'arrête pas les autres) -> agrégation -> import."""
    sources = sources if sources is not None else DEFAULT_SOURCES
    raw, out = Path(raw_dir), Path(out_dir)
    results = [extract_task(name, raw, params) for name, params in sources.items()]
    failed = [r for r in results if r["status"] != "success"]
    if failed:
        logger.warning("Sources en échec : {}", [(r["source"], r["message"]) for r in failed])
    report = aggregate_task(raw, out)
    loaded = load_task(out) if load_db else None
    return {"extractions": results, "aggregation": report, "import": loaded}
