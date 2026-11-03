"""Résumé d'une collecte (rapport JSON du flow + comptage en base) au format Markdown.

Utilisé par le workflow ``collecte`` (résumé de la page GitHub Actions) et par la documentation E1 :
les volumes cités dans le rapport viennent de ce tableau, pas d'estimations.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

TABLES = ("composant", "offre", "fournisseur", "fabricant", "bibliotheque", "execution_collecte")


def db_counts() -> dict[str, int]:
    from microforge.api_data import db

    models = {
        "composant": db.Component,
        "offre": db.Offer,
        "fournisseur": db.Supplier,
        "fabricant": db.Manufacturer,
        "bibliotheque": db.Library,
        "execution_collecte": db.IngestionRun,
    }
    with Session(db.get_engine()) as session:
        return {
            name: int(session.exec(select(func.count()).select_from(model)).one())
            for name, model in models.items()
        }


def markdown(report: dict[str, Any], counts: dict[str, int] | None = None) -> str:
    lines = ["## Collecte MicroForge", "", "| Source | Statut | Lignes | Durée (s) | Message |"]
    lines.append("|---|---|---:|---:|---|")
    for e in report.get("extractions", []):
        msg = (e.get("message") or "").replace("|", "/")[:90]
        lines.append(
            f"| {e['source']} | {e['status']} | {e['rows']} | {e.get('duration_s', '')} | {msg} |"
        )
    agg = report.get("aggregation") or {}
    lines += [
        "",
        "| Agrégation | Valeur |",
        "|---|---:|",
        *(
            f"| {k} | {agg[k]} |"
            for k in (
                "rows_in",
                "components_out",
                "offers_out",
                "rejected_total",
                "matched_catalog",
                "related_catalog",
                "libraries_out",
            )
            if k in agg
        ),
    ]
    for rule, n in (agg.get("rejected_by_rule") or {}).items():
        lines.append(f"| rejet {rule} | {n} |")
    if counts:
        lines += ["", "| Table | Lignes en base |", "|---|---:|"]
        lines += [f"| {t} | {counts[t]} |" for t in TABLES if t in counts]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> None:
    report = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    counts = db_counts() if report.get("import") else None
    if counts:
        report["db_counts"] = counts
        Path(argv[0]).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.stdout.write(markdown(report, counts))


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:])
