"""Import du jeu de données nettoyé dans la base (C4) — idempotent, tracé dans ``execution_collecte``."""

from __future__ import annotations

from datetime import UTC, datetime
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
    "LCSC": "base de données",
    "Boutique exemple": "scraping",
}


def _manufacturer_id(session: Session, name: str | None) -> int | None:
    if not name:
        return None
    row = session.exec(select(Manufacturer).where(Manufacturer.name == name)).first()
    if row is None:
        row = Manufacturer(name=name)
        session.add(row)
        session.flush()
    return row.id


def _supplier_id(session: Session, name: str) -> int:
    row = session.exec(select(Supplier).where(Supplier.name == name)).first()
    if row is None:
        row = Supplier(name=name, collection_method=SUPPLIER_METHODS.get(name, "scraping"))
        session.add(row)
        session.flush()
    return row.id  # type: ignore[return-value]


def import_clean(
    session: Session,
    components: list[dict[str, Any]],
    offers: list[dict[str, Any]],
    libraries: list[dict[str, Any]] | None = None,
) -> IngestionRun:
    run = IngestionRun(flow="import", source="aggregate", rows_in=len(components) + len(offers))
    session.add(run)
    sync_catalog(session)
    for cid, label in CATEGORY_LABELS.items():
        if session.get(Category, cid) is None:
            session.add(Category(id=cid, label=label))
    written = 0
    keys: dict[str, str] = {}
    for c in components:
        cid = c.get("catalog_id") or c["component_key"]
        keys[c["component_key"]] = cid
        row = session.get(Component, cid)
        if row is None:
            row = Component(
                id=cid,
                name=(c.get("name") or cid)[:200],
                category_id=c.get("category") or "passif",
                source=(c.get("sources") or ["pipeline"])[0],
            )
        # Les champs du catalogue maître ne sont pas écrasés ; on complète ce qui manque.
        row.mpn = row.mpn or c.get("mpn")
        row.manufacturer_id = row.manufacturer_id or _manufacturer_id(
            session, c.get("manufacturer")
        )
        row.package = row.package or c.get("package")
        row.datasheet_url = row.datasheet_url or c.get("datasheet_url")
        if row.supply_min_v is None and c.get("supply_min_v") is not None:
            row.supply_min_v, row.supply_max_v = c["supply_min_v"], c["supply_max_v"]
        if not row.interfaces and c.get("interfaces"):
            row.interfaces = c["interfaces"]
        row.updated_at = datetime.now(UTC)
        session.add(row)
        written += 1
    session.flush()
    for o in offers:
        cid = keys.get(o["component_key"], o["component_key"])
        sid = _supplier_id(session, o["supplier"])
        existing = session.exec(
            select(Offer).where(Offer.supplier_id == sid, Offer.sku == o.get("sku"))
        ).first()
        row = existing or Offer(
            component_id=cid, supplier_id=sid, sku=o.get("sku"), unit_price_eur=o["unit_price_eur"]
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
    for lib in libraries or []:
        row = session.get(Library, lib["name"]) or Library(name=lib["name"])
        row.latest_version = lib.get("version")
        row.architectures = ",".join(lib.get("architectures", []))
        row.includes = ",".join(lib.get("includes", []))
        row.repository = lib.get("repository")
        session.add(row)
    run.rows_out = written
    run.status = "success"
    run.finished_at = datetime.now(UTC)
    session.add(run)
    session.commit()
    logger.info("Import : {} lignes écrites", written)
    return run
