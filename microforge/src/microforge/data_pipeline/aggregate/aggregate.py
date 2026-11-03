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
  R5 prix_aberrant       : log10(prix) hors [Q1 − 3·IQR, Q3 + 3·IQR] dans sa sous-catégorie (≥ 8 offres).
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


KNOWN_CATEGORIES = {
    "carte", "capteur", "afficheur", "actionneur", "entree", "communication", "stockage",
    "passif", "discret", "ci", "alimentation", "consommable", "outillage",
}  # fmt: skip


def guess_category(*texts: str | None) -> str:
    if (
        texts and texts[0] in KNOWN_CATEGORIES
    ):  # source déjà classée (ex. LCSC via sa sous-catégorie)
        return texts[0]  # type: ignore[return-value]
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
    libraries_out: int = 0
    related_catalog: int = 0  # même référence que le catalogue mais autre objet (puce vs module)

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
            "libraries_out": self.libraries_out,
            "related_catalog": self.related_catalog,
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
    def match_catalog(self, name: str | None, mpn: str | None, by_name: bool = True) -> str | None:
        """MPN puis nom ; ``by_name=False`` pour les descriptions longues des catalogues de
        distributeurs (« LED driver… » ne doit pas être rapproché du composant « LED »)."""
        for candidate in (mpn, name) if by_name else (mpn,):
            if candidate:
                found = self.catalog.resolve_fuzzy(candidate)
                if found:
                    return found
        if not name or not by_name:
            return None
        best = process.extractOne(normalize(name), list(self._choices), scorer=fuzz.token_set_ratio)
        if best and best[1] >= self.threshold:
            return self._choices[best[0]]
        return None

    def _catalog_category(self, catalog_id: str) -> str:
        if catalog_id in self.catalog.boards:
            return "carte"
        return self.catalog.components[catalog_id].category

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
            extra = rec.get("extra") or {}
            catalog_id = self.match_catalog(name, mpn, extra.get("match_by_name", True))
            related = None
            src_cat = rec.get("category") if rec.get("category") in KNOWN_CATEGORIES else None
            if catalog_id and src_cat and self._catalog_category(catalog_id) != src_cat:
                # Même référence, autre objet : la puce ATMEGA328P n'est pas la carte Arduino Uno,
                # le capteur BME280 nu n'est pas le module. On garde le lien sans fusionner.
                related, catalog_id = catalog_id, None
                report.related_catalog += 1
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
                    "description": clean_text(rec.get("description")),
                    "related_catalog_id": related,
                    # Grandeur principale des passifs (résistance en Ω, capacité en F) : stock par valeur
                    "value": float(extra["value"]) if extra.get("value") is not None else None,
                    "value_unit": extra.get("value_unit"),
                    "value_text": extra.get("value_text"),
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
                    # Groupe de comparaison des prix (R5) : la sous-catégorie du distributeur si
                    # elle est connue (un microcontrôleur ne se compare pas à un ampli op).
                    "price_group": extra.get("lcsc_category") or comp["category"],
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
        """Prix hors [Q1 − 3·IQR, Q3 + 3·IQR] **en échelle log10**, par groupe d'au moins 8 offres.

        Les prix de composants suivent une loi proche de la log-normale (0,01 € à 50 €) : en échelle
        linéaire, toute pièce chère passerait pour aberrante ; en log, seuls les écarts d'ordres de
        grandeur (prix saisi en centimes, en lots de 1 000…) sont écartés.
        """
        import math
        import statistics

        by_group: dict[str, list[float]] = defaultdict(list)
        for o in offers:
            by_group[o.get("price_group") or o["category"]].append(math.log10(o["unit_price_eur"]))
        bounds = {}
        for group, logs in by_group.items():
            if len(logs) >= 8:
                q = statistics.quantiles(logs, n=4)
                iqr = q[2] - q[0]
                bounds[group] = (q[0] - 3 * iqr, q[2] + 3 * iqr)
        kept = []
        for o in offers:
            lo, hi = bounds.get(
                o.get("price_group") or o["category"], (float("-inf"), float("inf"))
            )
            if lo <= math.log10(o["unit_price_eur"]) <= hi:
                kept.append(o)
            else:
                report.reject("prix_aberrant", {"source": o["supplier"], "source_ref": o["sku"]})
        return kept


def latest_rows(raw_dir: Path, source: str) -> list[dict]:
    """Enregistrements du lot le plus récent d'une source (liste vide si jamais collectée)."""
    src_dir = raw_dir / source
    if not src_dir.is_dir():
        return []
    days = sorted(d for d in src_dir.iterdir() if (d / "records.jsonl").exists())
    if not days:
        return []
    lines = (days[-1] / "records.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def fritzing_to_raw(part: dict[str, Any]) -> dict[str, Any]:
    """Pièce Fritzing (définition de composant, sans prix) -> enregistrement commun."""
    props = {str(k).lower(): v for k, v in (part.get("properties") or {}).items()}
    return {
        "source": "fritzing",
        "source_ref": part.get("module_id") or part.get("file"),
        "name": part.get("title"),
        "mpn": props.get("part number") or props.get("mpn"),
        "description": " ".join(filter(None, [part.get("family"), *part.get("tags", [])])),
        "category": None,
        "package": props.get("package"),
        "supply_text": props.get("voltage"),
        "extra": {"match_by_name": True, "connectors": len(part.get("connectors") or [])},
    }


def load_raw(
    raw_dir: Path, sources: list[str] | None = None
) -> tuple[list[dict], dict[str, float]]:
    """Composants/offres (dernier lot de chaque source) et taux de change.

    Les sources « pièces » (``source_ref``) entrent telles quelles ; Fritzing est converti au format
    commun ; les bibliothèques (index Arduino, GitHub) sont traitées par :func:`load_libraries`.
    """
    records: list[dict] = []
    fx: dict[str, float] = {}
    if not raw_dir.is_dir():
        return records, fx
    for src_dir in sorted(p for p in raw_dir.iterdir() if p.is_dir()):
        if sources and src_dir.name not in sources and src_dir.name != "fx":
            continue
        rows = latest_rows(raw_dir, src_dir.name)
        if src_dir.name == "fx":
            fx = {r["currency"]: r["eur_per_unit"] for r in rows}
        elif src_dir.name == "fritzing":
            records += [fritzing_to_raw(r) for r in rows]
        elif rows and "source_ref" in rows[0]:
            records += rows
    return records, fx


def load_libraries(raw_dir: Path) -> list[dict[str, Any]]:
    """Index Arduino (dernière version de chaque bibliothèque) enrichi des étoiles GitHub (C3)."""
    stars: dict[str, int] = {}
    for row in latest_rows(raw_dir, "github"):
        key = normalize(row.get("library") or "")
        if row.get("stars") is not None:
            stars[key] = max(stars.get(key, 0), int(row["stars"]))
    out = []
    for lib in latest_rows(raw_dir, "arduino_index"):
        out.append(
            {
                "name": lib["name"],
                "version": lib.get("version"),
                "architectures": lib.get("architectures") or [],
                "includes": lib.get("includes") or [],
                "repository": lib.get("repository"),
                "category": lib.get("category"),
                "stars": stars.get(normalize(lib["name"])),
            }
        )
    return out


def write_outputs(
    components: list[dict],
    offers: list[dict],
    report: AggregationReport,
    out_dir: Path,
    libraries: list[dict] | None = None,
) -> None:
    import polars as pl

    out_dir.mkdir(parents=True, exist_ok=True)
    if libraries:
        pl.DataFrame(libraries, infer_schema_length=None).write_parquet(
            out_dir / "libraries_clean.parquet"
        )
        report.libraries_out = len(libraries)
    # Schéma déduit de TOUTES les lignes (valeurs entières puis décimales dans une même colonne).
    pl.DataFrame(
        [{**c, "sources": ",".join(c["sources"])} for c in components], infer_schema_length=None
    ).write_parquet(out_dir / "components_clean.parquet")
    if offers:
        pl.DataFrame(offers, infer_schema_length=None).write_parquet(
            out_dir / "offers_clean.parquet"
        )
    (out_dir / "rejects_report.json").write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
