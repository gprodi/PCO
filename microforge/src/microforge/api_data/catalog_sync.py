"""Synchronise le catalogue YAML du cœur dans la base (catégories, composants, cartes, bibliothèques)."""

from __future__ import annotations

from sqlmodel import Session, select

from microforge.api_data.db import Category, Component, ComponentLibrary, Library, utcnow
from microforge.core.catalog import Catalog, get_catalog
from microforge.core.models import SignalRole

CATEGORY_LABELS = {
    "carte": "Cartes microcontrôleurs",
    "capteur": "Capteurs",
    "afficheur": "Afficheurs",
    "actionneur": "Actionneurs",
    "entree": "Entrées utilisateur",
    "communication": "Communication",
    "stockage": "Stockage",
    "passif": "Composants passifs",
    "discret": "Semi-conducteurs discrets",
    "ci": "Circuits intégrés",
    "consommable": "Connectique et consommables",
    "outillage": "Outillage",
    "alimentation": "Alimentation",
}


def _interfaces(comp) -> str:
    roles = {p.role for p in comp.pins}
    tags = []
    if roles & {SignalRole.I2C_SDA, SignalRole.I2C_SCL}:
        tags.append("I2C")
    if roles & {SignalRole.SPI_MOSI, SignalRole.SPI_SCK, SignalRole.SPI_CS}:
        tags.append("SPI")
    if SignalRole.ADC in roles:
        tags.append("ADC")
    if SignalRole.PWM in roles:
        tags.append("PWM")
    if roles & {SignalRole.GPIO_IN, SignalRole.GPIO_OUT, SignalRole.GPIO_IO}:
        tags.append("GPIO")
    return ",".join(tags)


def sync_catalog(session: Session, catalog: Catalog | None = None) -> int:
    """Upsert idempotent ; renvoie le nombre de composants écrits."""
    catalog = catalog or get_catalog()
    for cid, label in CATEGORY_LABELS.items():
        if session.get(Category, cid) is None:
            session.add(Category(id=cid, label=label))
    session.flush()
    count = 0
    for b in catalog.boards.values():
        row = session.get(Component, b.id) or Component(id=b.id, name=b.name, category_id="carte")
        row.name, row.description = b.name, b.mcu
        row.supply_min_v = row.supply_max_v = b.logic_v
        row.interfaces = "I2C,SPI,UART,ADC,PWM" + (",WiFi" if b.wifi else "")
        row.reference_price_eur = b.price_eur
        row.updated_at = utcnow()
        session.add(row)
        count += 1
    for c in catalog.components.values():
        row = session.get(Component, c.id) or Component(
            id=c.id, name=c.name, category_id=c.category
        )
        row.name, row.category_id, row.description = c.name, c.category, c.description
        row.supply_min_v, row.supply_max_v = c.supply_v
        row.interfaces = _interfaces(c)
        row.reference_price_eur = c.price_eur
        row.updated_at = utcnow()
        session.add(row)
        count += 1
        for lib in {lib for tpl in c.code.values() for lib in tpl.libraries}:
            if session.get(Library, lib) is None:
                session.add(Library(name=lib))
            session.flush()
            exists = session.exec(
                select(ComponentLibrary).where(
                    ComponentLibrary.component_id == c.id, ComponentLibrary.library_name == lib
                )
            ).first()
            if exists is None:
                session.add(ComponentLibrary(component_id=c.id, library_name=lib))
    session.commit()
    return count
