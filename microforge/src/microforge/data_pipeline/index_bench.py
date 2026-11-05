"""C2 / C4 — Effet des index sur les requêtes réelles de l'application (PostgreSQL).

Pour chaque requête : plan et temps d'exécution (``EXPLAIN ANALYZE``, médiane de plusieurs passages)
avec et sans l'index étudié.

- Index existant : la mesure « sans » se fait après ``DROP INDEX`` dans une transaction annulée
  (``ROLLBACK``) ; la base n'est jamais modifiée.
- Index candidat : la mesure « avec » se fait après sa création dans une transaction annulée.

Les paramètres sont tirés des données (composant médian, sa référence fabricant, sa catégorie) pour
mesurer un cas représentatif et non un cas choisi pour flatter l'index.

    uv run mf-pipeline bench-index --runs 7 --out data/index_bench.json
"""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import Connection, Engine, text


@dataclass(frozen=True)
class Case:
    name: str
    usage: str
    sql: str
    index: str
    #: « existant » : index du schéma, retiré pour la mesure « sans » ;
    #: « candidat » : index proposé, créé pour la mesure « avec ».
    mode: str = "existant"
    create: tuple[str, ...] = ()


CASES: tuple[Case, ...] = (
    Case(
        "offres_d_un_composant",
        "GET /v1/components/{id}/offers",
        "SELECT o.id, o.unit_price_eur, f.name FROM offre AS o "
        "JOIN fournisseur AS f ON f.id = o.supplier_id "
        "WHERE o.component_id = :component_id ORDER BY o.unit_price_eur",
        "ix_offre_component_id",
    ),
    Case(
        "composant_par_reference",
        "rapprochement d'une offre par référence fabricant (MPN)",
        "SELECT id, name FROM composant WHERE mpn = :mpn",
        "ix_composant_mpn",
    ),
    Case(
        "composants_d_une_categorie",
        "GET /v1/components?category=…",
        "SELECT id, name FROM composant WHERE category_id = :category "
        "ORDER BY category_id, id LIMIT 50",
        "ix_composant_category_id",
    ),
    Case(
        "composants_d_une_categorie_tries",
        "GET /v1/components?category=… (filtre et tri servis par le même index)",
        "SELECT id, name FROM composant WHERE category_id = :category "
        "ORDER BY category_id, id LIMIT 50",
        "ix_composant_category_id_id",
        mode="candidat",
        create=(
            "CREATE INDEX ix_composant_category_id_id ON composant (category_id, id)",
            "ANALYZE composant",
        ),
    ),
    Case(
        "recherche_dans_le_nom",
        "recherche « contient » sur le nom (GET /v1/components?q=…)",
        "SELECT id, name FROM composant WHERE name ILIKE :motif ORDER BY category_id, id LIMIT 50",
        "ix_composant_name_trgm",
        mode="candidat",
        create=(
            "CREATE EXTENSION IF NOT EXISTS pg_trgm",
            "CREATE INDEX ix_composant_name_trgm ON composant USING gin (name gin_trgm_ops)",
            "ANALYZE composant",
        ),
    ),
)

#: Paramètres représentatifs, lus dans les données (milieu de l'ordre des clés).
PARAMS_SQL = {
    "component_id": (
        "SELECT component_id FROM offre ORDER BY component_id "
        "OFFSET (SELECT count(*) / 2 FROM offre) LIMIT 1"
    ),
    "mpn": (
        "SELECT mpn FROM composant WHERE mpn IS NOT NULL ORDER BY id "
        "OFFSET (SELECT count(*) / 2 FROM composant WHERE mpn IS NOT NULL) LIMIT 1"
    ),
}
SEARCH_TERM = "bme280"


@dataclass
class Measure:
    median_ms: float
    runs_ms: list[float]
    plan: list[str]
    rows: int


@dataclass
class Result:
    case: str
    usage: str
    index: str
    mode: str
    params: dict[str, Any]
    without_index: Measure
    with_index: Measure
    gain: float = field(init=False)

    def __post_init__(self) -> None:
        self.gain = round(self.without_index.median_ms / max(self.with_index.median_ms, 1e-3), 1)


def scan_nodes(node: dict[str, Any]) -> list[str]:
    """Nœuds de lecture d'un plan JSON : « Seq Scan offre », « Index Scan ix_offre_component_id »."""
    out = []
    kind = node.get("Node Type", "")
    if "Scan" in kind:
        target = node.get("Index Name") or node.get("Relation Name") or ""
        out.append(f"{kind} {target}".strip())
    for child in node.get("Plans", []):
        out.extend(scan_nodes(child))
    return out


def _explain(conn: Connection, sql: str, params: dict[str, Any]) -> dict[str, Any]:
    raw = conn.execute(text("EXPLAIN (ANALYZE, FORMAT JSON) " + sql), params).scalar_one()
    doc = json.loads(raw) if isinstance(raw, str) else raw
    return doc[0]


def measure(conn: Connection, sql: str, params: dict[str, Any], runs: int) -> Measure:
    """Médiane du temps d'exécution côté serveur, après un passage de chauffe (cache chaud)."""
    _explain(conn, sql, params)
    plans = [_explain(conn, sql, params) for _ in range(runs)]
    times = [round(p["Execution Time"], 3) for p in plans]
    last = plans[-1]["Plan"]
    return Measure(
        median_ms=round(statistics.median(times), 3),
        runs_ms=times,
        plan=scan_nodes(last),
        rows=int(last.get("Actual Rows", 0)),
    )


def representative_params(conn: Connection) -> dict[str, Any]:
    params: dict[str, Any] = {k: conn.execute(text(q)).scalar() for k, q in PARAMS_SQL.items()}
    if params["component_id"] is None or params["mpn"] is None:
        raise ValueError("base vide : lancer d'abord la collecte et l'import (mf-pipeline run)")
    params["category"] = conn.execute(
        text("SELECT category_id FROM composant WHERE id = :id"), {"id": params["component_id"]}
    ).scalar()
    params["motif"] = f"%{SEARCH_TERM}%"
    return params


def run_case(engine: Engine, case: Case, params: dict[str, Any], runs: int) -> Result:
    used = {k: v for k, v in params.items() if f":{k}" in case.sql}
    with engine.connect() as conn:
        current = measure(conn, case.sql, used, runs)
        conn.rollback()
        trans = conn.begin()
        try:
            if case.mode == "existant":
                conn.execute(text(f"DROP INDEX {case.index}"))
            else:
                for ddl in case.create:
                    conn.execute(text(ddl))
            other = measure(conn, case.sql, used, runs)
        finally:
            trans.rollback()  # la base retrouve exactement son état
    without, with_ = (other, current) if case.mode == "existant" else (current, other)
    return Result(case.name, case.usage, case.index, case.mode, used, without, with_)


def table_sizes(engine: Engine) -> dict[str, int]:
    with engine.connect() as conn:
        return {
            # Noms de tables constants (aucune donnée extérieure dans la requête).
            t: int(conn.execute(text(f"SELECT count(*) FROM {t}")).scalar_one())  # noqa: S608
            for t in ("composant", "offre", "fournisseur", "categorie")
        }


def bench(engine: Engine, runs: int = 7) -> dict[str, Any]:
    if engine.dialect.name != "postgresql":
        raise ValueError("mesure prévue pour PostgreSQL (EXPLAIN ANALYZE au format JSON)")
    with engine.connect() as conn:
        params = representative_params(conn)
        version = conn.execute(text("SHOW server_version")).scalar_one()
    results = [run_case(engine, case, params, runs) for case in CASES]
    return {
        "postgresql": version,
        "runs": runs,
        "tables": table_sizes(engine),
        "results": [asdict(r) for r in results],
    }


def to_markdown(report: dict[str, Any]) -> str:
    sizes = ", ".join(f"{t} {n:,}".replace(",", " ") for t, n in report["tables"].items())
    lines = [
        "## Index : temps d'exécution avant / après",
        "",
        f"PostgreSQL {report['postgresql']} ; {sizes} lignes ; médiane de {report['runs']} "
        "passages EXPLAIN ANALYZE (cache chaud), index retiré ou créé dans une transaction annulée.",
        "",
        "| Requête | Usage | Index | Lignes | Sans index | Avec index | Gain |",
        "|---|---|---|---:|---|---|---:|",
    ]
    for r in report["results"]:
        idx = r["index"] + (" (candidat)" if r["mode"] == "candidat" else "")
        w, a = r["without_index"], r["with_index"]
        lines.append(
            f"| {r['case']} | {r['usage']} | {idx} | {a['rows']} "
            f"| {w['median_ms']:.3f} ms — {', '.join(w['plan'])} "
            f"| {a['median_ms']:.3f} ms — {', '.join(a['plan'])} | ×{r['gain']} |"
        )
    return "\n".join(lines) + "\n"
