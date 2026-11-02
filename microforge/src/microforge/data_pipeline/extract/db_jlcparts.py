"""Source base de données — jlcparts ``cache.sqlite3`` (catalogue JLCPCB/LCSC, ~11 Go).

Connexion programmatique (sqlite3 en lecture seule), exécution des requêtes SQL documentées
dans ``sql/`` (C2). Téléchargement : voir docs/E1/specifications.md (archives cache.zip / .zNN).
"""

from __future__ import annotations

import json
import sqlite3
from importlib import resources
from pathlib import Path
from typing import Any

from microforge.data_pipeline.base import ExtractionError, Extractor, RawPart, to_dict


def read_sql(name: str) -> str:
    return (
        resources.files("microforge.data_pipeline")
        .joinpath("sql", name)
        .read_text(encoding="utf-8")
    )


class JlcpartsExtractor(Extractor):
    source = "jlcparts"
    kind = "database"

    def setup(self) -> None:
        path = Path(self.params.get("path", "data/external/cache.sqlite3"))
        if not path.exists():
            raise ExtractionError(f"Base jlcparts introuvable : {path}")
        # Lecture seule : la base de référence ne doit jamais être modifiée par le pipeline.
        self.conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row

    def teardown(self) -> None:
        if getattr(self, "conn", None):
            self.conn.close()

    @staticmethod
    def first_price(price_json: str | None) -> float | None:
        try:
            tiers = json.loads(price_json or "[]")
        except json.JSONDecodeError:
            return None
        return tiers[0].get("price") if tiers else None

    def extract(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            read_sql("jlcparts_maker_parts.sql"),
            {
                "min_stock": int(self.params.get("min_stock", 100)),
                "max_rows": int(self.params.get("max_rows", 5000)),
            },
        ).fetchall()
        out = []
        for r in rows:
            out.append(
                to_dict(
                    RawPart(
                        source="jlcparts",
                        source_ref=f"C{r['lcsc']}",
                        name=r["description"],
                        mpn=r["mpn"],
                        manufacturer=r["manufacturer"],
                        description=r["description"],
                        category=f"{r['category']} / {r['subcategory']}",
                        package=r["package"],
                        price=self.first_price(r["price_json"]),
                        currency="USD",
                        stock=r["stock"],
                        url=f"https://www.lcsc.com/product-detail/C{r['lcsc']}.html",
                        datasheet_url=r["datasheet_url"],
                        supplier="LCSC",
                        extra={"basic": bool(r["is_basic"]), "price_tiers": r["price_json"]},
                    )
                )
            )
        return out

    def explain(self) -> list[str]:
        """Plan d'exécution (documentation des optimisations C2)."""
        plan = self.conn.execute(
            "EXPLAIN QUERY PLAN " + read_sql("jlcparts_maker_parts.sql"),
            {"min_stock": 100, "max_rows": 10},
        ).fetchall()
        return [row[3] for row in plan]
