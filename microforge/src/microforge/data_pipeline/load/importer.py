"""Import du jeu de données nettoyé dans la base (C4) — idempotent, tracé dans ``execution_collecte``."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger
from sqlmodel import Session, select

from microforge.api_data.catalog_sync import CATEGORY_LABELS, sync_catalog
from microforge.api_data.db import (
    Category,
    Component,
    IngestionRun,
    Library,
    Manufacturer,
    Offer,
    Supplier,
)

SUPPLIER_METHODS = {
    "DigiKey": "api",
    "Mouser": "api",
    "LCSC": "fichiers jlcparts (JSONL ou SQLite)",
    "Boutique exemple": "scraping",
}
BATCH = 2000  # flush régulier : imports de plusieurs dizaines de milliers de lignes


class _Index:
    """Clés déjà en base, chargées une fois (évite une requête par ligne importée)."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.manufacturers = {m.name: m.id for m in session.exec(select(Manufacturer))}
        self.suppliers = {s.name: s.id for s in session.exec(select(Supplier))}
        self.components = set(session.exec(select(Component.id)))
        self.offers = {
            (sid, sku): oid
            for oid, sid, sku in session.exec(select(Offer.id, Offer.supplier_id, Offer.sku))
        }

    def manufacturer(self, name: str | None) -> int | None:
        if not name:
            return None
        if name not in self.manufacturers:
            row = Manufacturer(name=name)
            self.session.add(row)
            self.session.flush()
            self.manufacturers[name] = row.id
        return self.manufacturers[name]

    def supplier(self, name: str) -> int:
        if name not in self.suppliers:
            row = Supplier(name=name, collection_method=SUPPLIER_METHODS.get(name, "scraping"))
            self.session.add(row)
            self.session.flush()
            self.suppliers[name] = row.id
        return self.suppliers[name]  # type: ignore[return-value]


def import_clean(
    session: Session,
    components: list[dict[str, Any]],
    offers: list[dict[str, Any]],
    libraries: list[dict[str, Any]] | None = None,
) -> IngestionRun:
    run = IngestionRun(
        flow="import",
        source="aggregate",
        rows_in=len(components) + len(offers) + len(libraries or []),
    )
    session.add(run)
    sync_catalog(session)
    for cid, label in CATEGORY_LABELS.items():
        if session.get(Category, cid) is None:
            session.add(Category(id=cid, label=label))
    session.flush()
    idx = _Index(session)
    written = 0
    keys: dict[str, str] = {}
    for i, c in enumerate(components, start=1):
        cid = (c.get("catalog_id") or c["component_key"])[:60]
        keys[c["component_key"]] = cid
        row = session.get(Component, cid) if cid in idx.components else None
        if row is None:
            row = Component(
                id=cid,
                name=(c.get("name") or cid)[:200],
                category_id=c.get("category") if c.get("category") in CATEGORY_LABELS else "passif",
                source=(c.get("sources") or ["pipeline"])[0],
            )
            idx.components.add(cid)
        # Les champs du catalogue maître ne sont pas écrasés ; on complète ce qui manque.
        row.mpn = row.mpn or ((c.get("mpn") or None) and c["mpn"][:80])
        row.manufacturer_id = row.manufacturer_id or idx.manufacturer(c.get("manufacturer"))
        row.package = row.package or c.get("package")
        row.datasheet_url = row.datasheet_url or c.get("datasheet_url")
        row.description = row.description or (c.get("value_text") or c.get("description") or "")
        if row.supply_min_v is None and c.get("supply_min_v") is not None:
            row.supply_min_v, row.supply_max_v = c["supply_min_v"], c["supply_max_v"]
        if not row.interfaces and c.get("interfaces"):
            row.interfaces = c["interfaces"]
        row.updated_at = datetime.now(UTC)
        session.add(row)
        written += 1
        if i % BATCH == 0:
            session.flush()
    session.flush()
    for i, o in enumerate(offers, start=1):
        cid = keys.get(o["component_key"], o["component_key"][:60])
        sid = idx.supplier(o["supplier"])
        oid = idx.offers.get((sid, o.get("sku")))
        row = session.get(Offer, oid) if oid else None
        if row is None:
            row = Offer(
                component_id=cid,
                supplier_id=sid,
                sku=o.get("sku"),
                unit_price_eur=o["unit_price_eur"],
            )
        row.unit_price_eur = o["unit_price_eur"]
        row.price_original = o.get("price_original")
        row.currency_original = o.get("currency_original", "EUR")
        row.stock = o.get("stock")
        row.url = o.get("url") or ""
        row.collected_at = (
            datetime.fromisoformat(o["collected_at"])
            if o.get("collected_at")
            else datetime.now(UTC)
        )
        session.add(row)
        written += 1
        if i % BATCH == 0:
            session.flush()
    for lib in libraries or []:
        row = session.get(Library, lib["name"][:120]) or Library(name=lib["name"][:120])
        row.latest_version = lib.get("version")
        row.architectures = ",".join(lib.get("architectures") or [])
        row.includes = ",".join(lib.get("includes") or [])
        row.repository = lib.get("repository")
        row.stars = lib.get("stars") if lib.get("stars") is not None else row.stars
        session.add(row)
        written += 1
    run.rows_out = written
    run.status = "success"
    run.finished_at = datetime.now(UTC)
    session.add(run)
    session.commit()
    logger.info("Import : {} lignes écrites", written)
    return run


def read_clean(clean_dir: Path) -> tuple[list[dict], list[dict], list[dict]]:
    """Relit les Parquet produits par l'agrégation (composants, offres, bibliothèques)."""
    import polars as pl

    comps = pl.read_parquet(clean_dir / "components_clean.parquet").to_dicts()
    for c in comps:
        c["sources"] = (c.get("sources") or "").split(",")

    def optional(name: str) -> list[dict]:
        path = clean_dir / name
        return pl.read_parquet(path).to_dicts() if path.exists() else []

    return comps, optional("offers_clean.parquet"), optional("libraries_clean.parquet")
