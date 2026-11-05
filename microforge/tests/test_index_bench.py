"""Mesure de l'effet des index (C2/C4) : plans, rendu, et exécution réelle sur PostgreSQL.

Le test d'intégration (marqueur ``pgvector``, job CI PostgreSQL) crée une base temporaire, la remplit
de données synthétiques, mesure, puis vérifie que la base est restée intacte (index et extensions).
"""

from __future__ import annotations

import os
import uuid

import pytest
from microforge.data_pipeline.index_bench import (
    CASES,
    Measure,
    Result,
    bench,
    scan_nodes,
    to_markdown,
)
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

PLAN = {
    "Node Type": "Sort",
    "Plans": [
        {
            "Node Type": "Hash Join",
            "Plans": [
                {
                    "Node Type": "Bitmap Heap Scan",
                    "Relation Name": "offre",
                    "Plans": [
                        {"Node Type": "Bitmap Index Scan", "Index Name": "ix_offre_component_id"}
                    ],
                },
                {
                    "Node Type": "Hash",
                    "Plans": [{"Node Type": "Seq Scan", "Relation Name": "fournisseur"}],
                },
            ],
        }
    ],
}


def test_scan_nodes_lists_every_read_in_plan_order():
    assert scan_nodes(PLAN) == [
        "Bitmap Heap Scan offre",
        "Bitmap Index Scan ix_offre_component_id",
        "Seq Scan fournisseur",
    ]


def test_gain_is_ratio_of_medians_and_never_divides_by_zero():
    slow = Measure(median_ms=5.0, runs_ms=[5.0], plan=["Seq Scan offre"], rows=3)
    fast = Measure(median_ms=0.05, runs_ms=[0.05], plan=["Index Scan ix"], rows=3)
    assert Result("c", "u", "ix", "existant", {}, slow, fast).gain == 100.0
    zero = Measure(median_ms=0.0, runs_ms=[0.0], plan=[], rows=0)
    assert Result("c", "u", "ix", "existant", {}, slow, zero).gain == 5000.0


def test_cases_target_real_schema_indexes_or_declare_their_ddl():
    existing = {c.index for c in CASES if c.mode == "existant"}
    assert existing == {"ix_offre_component_id", "ix_composant_mpn", "ix_composant_category_id"}
    for case in CASES:
        assert case.mode in {"existant", "candidat"}
        if case.mode == "candidat":
            assert any(case.index in ddl for ddl in case.create)
        assert case.sql.lstrip().upper().startswith("SELECT")


def test_markdown_table():
    report = {
        "postgresql": "17.6",
        "runs": 7,
        "tables": {"composant": 93521, "offre": 100413},
        "results": [
            {
                "case": "offres_d_un_composant",
                "usage": "GET /v1/components/{id}/offers",
                "index": "ix_offre_component_id",
                "mode": "existant",
                "without_index": {"median_ms": 5.4, "plan": ["Seq Scan offre"], "rows": 1},
                "with_index": {
                    "median_ms": 0.08,
                    "plan": ["Index Scan ix_offre_component_id"],
                    "rows": 1,
                },
                "gain": 67.5,
            }
        ],
    }
    md = to_markdown(report)
    assert "composant 93 521, offre 100 413 lignes" in md
    assert (
        "| 5.400 ms — Seq Scan offre | 0.080 ms — Index Scan ix_offre_component_id | ×67.5 |" in md
    )


def test_refuses_sqlite():
    with pytest.raises(ValueError, match="PostgreSQL"):
        bench(create_engine("sqlite://"))


# ------------------------------------------------------------------ PostgreSQL réel
PG_URL = os.environ.get("PGVECTOR_TEST_URL")


@pytest.mark.pgvector
@pytest.mark.skipif(not PG_URL, reason="PGVECTOR_TEST_URL non défini (base PostgreSQL)")
def test_bench_on_postgresql_leaves_database_untouched():
    from microforge.api_data.db import init_db

    name = f"mf_bench_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    engine = create_engine(make_url(PG_URL).set(database=name))
    try:
        init_db(engine)
        with engine.begin() as c:
            c.execute(
                text(
                    "INSERT INTO categorie (id, label) SELECT 'cat' || g, 'Cat' FROM generate_series(1, 20) g"
                )
            )
            c.execute(
                text(
                    "INSERT INTO fournisseur (name, url, country, collection_method) VALUES ('LCSC', '', 'CN', 'api')"
                )
            )
            c.execute(
                text(
                    "INSERT INTO composant (id, name, category_id, mpn, description, interfaces, source, updated_at) "
                    "SELECT 'c' || g, 'Part ' || g || CASE WHEN g % 500 = 0 THEN ' BME280' ELSE '' END, "
                    "'cat' || (1 + g % 20), 'MPN' || g, '', '', 'lcsc', now() FROM generate_series(1, 5000) g"
                )
            )
            c.execute(
                text(
                    "INSERT INTO offre (component_id, supplier_id, unit_price_eur, currency_original, url, collected_at) "
                    "SELECT 'c' || (1 + g % 5000), 1, g / 100.0, 'EUR', '', now() FROM generate_series(1, 8000) g"
                )
            )
            c.execute(text("ANALYZE"))
        indexes = "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' ORDER BY 1"
        with engine.connect() as c:
            before = c.execute(text(indexes)).scalars().all()

        report = bench(engine, runs=2)

        assert report["tables"]["composant"] == 5000 and report["tables"]["offre"] == 8000
        by_case = {r["case"]: r for r in report["results"]}
        assert set(by_case) == {c.name for c in CASES}
        mpn = by_case["composant_par_reference"]
        assert mpn["with_index"]["plan"] == ["Index Scan ix_composant_mpn"]
        assert mpn["without_index"]["plan"] == ["Seq Scan composant"]
        assert mpn["with_index"]["rows"] == 1
        trgm = by_case["recherche_dans_le_nom"]
        assert any("ix_composant_name_trgm" in n for n in trgm["with_index"]["plan"])
        assert trgm["with_index"]["rows"] == 10
        # Transactions annulées : mêmes index, pas d'extension pg_trgm laissée derrière.
        with engine.connect() as c:
            assert c.execute(text(indexes)).scalars().all() == before
            assert not c.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")
            ).first()
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()
