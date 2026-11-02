"""CLI du pipeline E1 : ``mf-pipeline extract | aggregate | load | purge | run``."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from sqlmodel import Session

app = typer.Typer(help="Pipeline de données MicroForge (E1).", no_args_is_help=True)


@app.command()
def extract(
    source: str,
    raw_dir: Path = typer.Option(Path("data/raw")),
    path: str = typer.Option(
        None, help="fichier/dossier local (arduino_index, fritzing, jlcparts)"
    ),
    keywords: str = typer.Option(None, help="mots-clés séparés par des virgules (APIs)"),
    shop: str = typer.Option("exemple", help="boutique de shops.yaml"),
) -> None:
    """Exécute un extracteur (digikey, mouser, github, fx, arduino_index, fritzing, shop, jlcparts)."""
    from microforge.data_pipeline.extract import EXTRACTORS

    params: dict = {}
    if path:
        params["path"] = path
    if keywords:
        params["keywords"] = [k.strip() for k in keywords.split(",")]
    if source == "shop":
        params["shop"] = shop
    _, manifest = EXTRACTORS[source](out_dir=raw_dir, **params).run()
    typer.echo(json.dumps(manifest.__dict__, ensure_ascii=False, indent=2))
    if manifest.status != "success":
        raise typer.Exit(code=1)


@app.command()
def aggregate(
    raw_dir: Path = typer.Option(Path("data/raw")), out_dir: Path = typer.Option(Path("data/clean"))
) -> None:
    """Agrège et nettoie le dernier lot de chaque source (C3)."""
    from microforge.data_pipeline.aggregate.aggregate import Aggregator, load_raw, write_outputs

    records, fx = load_raw(raw_dir)
    components, offers, report = Aggregator(fx).run(records)
    write_outputs(components, offers, report, out_dir)
    typer.echo(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


@app.command()
def load(clean_dir: Path = typer.Option(Path("data/clean"))) -> None:
    """Importe le jeu nettoyé dans la base (C4)."""
    import polars as pl

    from microforge.api_data.db import get_engine, init_db
    from microforge.data_pipeline.load.importer import import_clean

    init_db()
    comps = pl.read_parquet(clean_dir / "components_clean.parquet").to_dicts()
    for c in comps:
        c["sources"] = (c.get("sources") or "").split(",")
    offers_path = clean_dir / "offers_clean.parquet"
    offers = pl.read_parquet(offers_path).to_dicts() if offers_path.exists() else []
    with Session(get_engine()) as session:
        run = import_clean(session, comps, offers)
    typer.echo(f"Import terminé : {run.rows_out} lignes")


@app.command()
def purge() -> None:
    """Procédure de tri RGPD (à planifier chaque semaine)."""
    from microforge.api_data.db import get_engine, init_db
    from microforge.data_pipeline.load.purge import purge as do_purge

    init_db()
    with Session(get_engine()) as session:
        typer.echo(json.dumps(do_purge(session), ensure_ascii=False))


@app.command()
def spark(
    parquet_dir: Path = typer.Option(Path("data/interim/lcsc_parquet")),
    sqlite: Path = typer.Option(None),
    driver_memory: str = "4g",
) -> None:
    """Big data : export Parquet (si --sqlite) puis statistiques Spark SQL."""
    from microforge.data_pipeline.extract.bigdata_spark import SparkCategoryStats, export_parquet

    if sqlite:
        export_parquet(sqlite, parquet_dir)
    _, manifest = SparkCategoryStats(
        parquet_dir=str(parquet_dir), driver_memory=driver_memory
    ).run()
    typer.echo(json.dumps(manifest.__dict__, ensure_ascii=False, indent=2))


@app.command()
def run(raw_dir: str = "data/raw", out_dir: str = "data/clean") -> None:
    """Flow complet (Prefect si installé)."""
    from microforge.data_pipeline.flows import collect_flow

    typer.echo(
        json.dumps(
            collect_flow(raw_dir=raw_dir, out_dir=out_dir),
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    app()
