"""Agrégation multi-sources -> jeu de données unique, nettoyé et normalisé (C3).

Enchaînement :

1. **union** des enregistrements bruts de toutes les sources (format ``RawPart``) ;
2. **nettoyage** des textes (HTML, espaces, Unicode) et normalisation des formats :
   MPN, fabricant, tension -> (min, max) V, boîtier, interfaces, prix -> EUR, stock -> entier, dates ISO ;
3. **détection et suppression des entrées corrompues** (règles R1–R5 ci-dessous), chaque rejet
   étant compté et illustré dans le rapport ;
4. **rapprochement** avec le catalogue MicroForge (alias puis similarité rapidfuzz ≥ 88) ;
5. **dédoublonnage** : une offre par (fournisseur, référence), la plus récente ;
6. **sorties** : ``components_clean``, ``offers_clean`` (Parquet) + ``rejects_report.json``.

Règles de rejet :
  R1 identite_manquante  : ni MPN ni nom ;
  R2 prix_invalide       : prix absent, nul ou négatif (offres) ;
  R3 devise_inconnue     : prix non convertible en EUR ;
  R4 stock_negatif       : stock < 0 ;
  R5 prix_aberrant       : hors [Q1 − 3·IQR, Q3 + 3·IQR] dans sa catégorie (si ≥ 8 offres).
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz, process

from microforge.core.catalog import Catalog, get_catalog, normalize
from microforge.data_pipeline.aggregate.rules import (
    clean_text,
    normalize_date,
    normalize_interfaces,
    normalize_manufacturer,
    normalize_mpn,
    normalize_package,
    parse_number,
    parse_stock,
    parse_voltage_range,
    to_eur,
)

CATEGORY_KEYWORDS = [
    (
        "carte",
        ["development board", "dev board", "microcontroller board", "arduino", "esp32", "pico"],
    ),
    ("afficheur", ["display", "oled", "lcd", "7-segment", "afficheur", "écran"]),
    (
        "capteur",
        [
            "sensor",
            "capteur",
            "accelerometer",
            "gyroscope",
            "humidity",
            "temperature",
            "ultrasonic",
            "pir",
        ],
    ),
    ("actionneur", ["motor", "servo", "relay", "relais", "buzzer", "led", "driver"]),
    ("communication", ["rfid", "nfc", "wireless", "bluetooth", "transceiver"]),
    ("stockage", ["sd card", "micro sd", "eeprom", "flash"]),
    ("passif", ["resistor", "capacitor", "résistance", "condensateur"]),
]


def guess_category(*texts: str | None) -> str:
    low = " ".join(t or "" for t in texts).lower()
    for cat, words in CATEGORY_KEYWORDS:
        if any(w in low for w in words):
            return cat
    return "capteur" if "module" in low else "passif"


@dataclass
class AggregationReport:
    rows_in: int = 0
    components_out: int = 0
    offers_out: int = 0
    rejected: Counter[str] = field(default_factory=Counter)
    examples: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    matched_catalog: int = 0
    duplicates_removed: int = 0

    def reject(self, rule: str, record: dict[str, Any]) -> None:
        self.rejected[rule] += 1
        if len(self.examples[rule]) < 5:
            self.examples[rule].append(f"{record.get('source')}:{record.get('source_ref')}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows_in": self.rows_in,
            "components_out": self.components_out,
            "offers_out": self.offers_out,
            "rejected_total": sum(self.rejected.values()),
            "rejected_by_rule": dict(self.rejected),
            "examples": dict(self.examples),
            "matched_catalog": self.matched_catalog,
            "duplicates_removed": self.duplicates_removed,
        }


class Aggregator:
    def __init__(
        self,
        fx: dict[str, float] | None = None,
        catalog: Catalog | None = None,
        threshold: int = 88,
    ) -> None:
        self.fx = {"EUR": 1.0, **(fx or {})}
        self.catalog = catalog or get_catalog()
        self.threshold = threshold
        self._choices: dict[str, str] = {}
        for item in [*self.catalog.components.values(), *self.catalog.boards.values()]:
            for label in [item.name, *item.aliases]:
                self._choices[normalize(label)] = item.id

    # ------------------------------------------------------------------ rapprochement
    def match_catalog(self, name: str | None, mpn: str | None) -> str | None:
        for candidate in (mpn, name):
            if candidate:
                found = self.catalog.resolve_fuzzy(candidate)
                if found:
                    return found
        if not name:
            return None
        best = process.extractOne(normalize(name), list(self._choices), scorer=fuzz.token_set_ratio)
        if best and best[1] >= self.threshold:
            return self._choices[best[0]]
        return None

    # ------------------------------------------------------------------ principal
    def run(
        self, records: list[dict[str, Any]]
    ) -> tuple[list[dict], list[dict], AggregationReport]:
        report = AggregationReport(rows_in=len(records))
        components: dict[str, dict[str, Any]] = {}
        offers: dict[tuple[str, str], dict[str, Any]] = {}

        for rec in records:
            name = clean_text(rec.get("name") or rec.get("description"))
            mpn = normalize_mpn(rec.get("mpn"))
            if not name and not mpn:  # R1
                report.reject("identite_manquante", rec)
                continue
            stock = parse_stock(rec.get("stock"))
            if stock is not None and stock < 0:  # R4
                report.reject("stock_negatif", rec)
                continue
            catalog_id = self.match_catalog(name, mpn)
            if catalog_id:
                report.matched_catalog += 1
                key = catalog_id
            else:
                slug = re.sub(r"[^a-z0-9]+", "-", (mpn or name or "").lower()).strip("-")[:50]
                key = f"{rec.get('source', 'src')}-{slug}"
            volts = parse_voltage_range(rec.get("supply_text"))
            comp = components.setdefault(
                key,
                {
                    "component_key": key,
                    "catalog_id": catalog_id,
                    "name": name,
                    "mpn": mpn,
                    "manufacturer": normalize_manufacturer(rec.get("manufacturer")),
                    "category": self.catalog.components[catalog_id].category
                    if catalog_id in self.catalog.components
                    else (
                        "carte"
                        if catalog_id in self.catalog.boards
                        else guess_category(rec.get("category"), name)
                    ),
                    "package": normalize_package(rec.get("package")),
                    "supply_min_v": volts[0] if volts else None,
                    "supply_max_v": volts[1] if volts else None,
                    "interfaces": normalize_interfaces(
                        " ".join(
                            filter(None, [rec.get("interfaces_text"), name, rec.get("description")])
                        )
                    ),
                    "datasheet_url": rec.get("datasheet_url"),
                    "sources": [],
                },
            )
            if rec.get("source") not in comp["sources"]:
                comp["sources"].append(rec.get("source"))
            # complète les champs manquants avec les autres sources
            for fld, val in (
                ("datasheet_url", rec.get("datasheet_url")),
                ("mpn", mpn),
                ("manufacturer", normalize_manufacturer(rec.get("manufacturer"))),
            ):
                if not comp.get(fld) and val:
                    comp[fld] = val

            if rec.get("supplier"):
                amount = parse_number(rec.get("price"))
                if amount is None or amount <= 0:  # R2
                    report.reject("prix_invalide", rec)
                    continue
                eur = to_eur(amount, rec.get("currency"), self.fx)
                if eur is None:  # R3
                    report.reject("devise_inconnue", rec)
                    continue
                offer = {
                    "component_key": key,
                    "category": comp["category"],
                    "supplier": rec["supplier"],
                    "sku": rec.get("source_ref"),
                    "unit_price_eur": eur,
                    "price_original": amount,
                    "currency_original": (rec.get("currency") or "EUR").upper(),
                    "stock": stock,
                    "url": rec.get("url") or "",
                    "collected_at": normalize_date(rec.get("collected_at")),
                }
                okey = (offer["supplier"], offer["sku"] or key)
                previous = offers.get(okey)
                if previous is not None:
                    report.duplicates_removed += 1
                    if (previous["collected_at"] or "") >= (offer["collected_at"] or ""):
                        continue
                offers[okey] = offer

        clean_offers = self._remove_price_outliers(list(offers.values()), report)
        report.components_out = len(components)
        report.offers_out = len(clean_offers)
        return list(components.values()), clean_offers, report

    @staticmethod
    def _remove_price_outliers(offers: list[dict], report: AggregationReport) -> list[dict]:  # R5
        import statistics

        by_cat: dict[str, list[float]] = defaultdict(list)
        for o in offers:
            by_cat[o["category"]].append(o["unit_price_eur"])
        bounds = {}
        for cat, prices in by_cat.items():
            if len(prices) >= 8:
                q = statistics.quantiles(prices, n=4)
                iqr = q[2] - q[0]
                bounds[cat] = (q[0] - 3 * iqr, q[2] + 3 * iqr)
        kept = []
        for o in offers:
            lo, hi = bounds.get(o["category"], (float("-inf"), float("inf")))
            if lo <= o["unit_price_eur"] <= hi:
                kept.append(o)
            else:
                report.reject("prix_aberrant", {"source": o["supplier"], "source_ref": o["sku"]})
        return kept


def load_raw(
    raw_dir: Path, sources: list[str] | None = None
) -> tuple[list[dict], dict[str, float]]:
    """Charge le dernier lot de chaque source (``records.jsonl``) et les taux de change."""
    records: list[dict] = []
    fx: dict[str, float] = {}
    for src_dir in sorted(p for p in raw_dir.iterdir() if p.is_dir()):
        if sources and src_dir.name not in sources and src_dir.name != "fx":
            continue
        days = sorted(d for d in src_dir.iterdir() if (d / "records.jsonl").exists())
        if not days:
            continue
        lines = (days[-1] / "records.jsonl").read_text(encoding="utf-8").splitlines()
        rows = [json.loads(line) for line in lines if line.strip()]
        if src_dir.name == "fx":
            fx = {r["currency"]: r["eur_per_unit"] for r in rows}
        elif rows and "source_ref" in rows[0]:
            records += rows
    return records, fx


def write_outputs(
    components: list[dict], offers: list[dict], report: AggregationReport, out_dir: Path
) -> None:
    import polars as pl

    out_dir.mkdir(parents=True, exist_ok=True)
    pl.DataFrame([{**c, "sources": ",".join(c["sources"])} for c in components]).write_parquet(
        out_dir / "components_clean.parquet"
    )
    if offers:
        pl.DataFrame(offers).write_parquet(out_dir / "offers_clean.parquet")
    (out_dir / "rejects_report.json").write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
