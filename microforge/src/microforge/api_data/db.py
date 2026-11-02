"""Modèle physique des données (SQLModel) — traduction du MCD Merise (docs/E1/merise.md).

PostgreSQL en production (+ pgvector pour les datasheets), SQLite en développement et en test.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from functools import lru_cache

from sqlalchemy import UniqueConstraint
from sqlalchemy.engine import Engine
from sqlmodel import Field, Session, SQLModel, create_engine

from microforge.common.settings import get_settings


def utcnow() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------ utilisateurs
class User(SQLModel, table=True):
    """Utilisateur. Données personnelles minimisées : e-mail chiffré, ville facultative."""

    __tablename__ = "utilisateur"
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, max_length=40)
    email_encrypted: str
    email_index: str = Field(index=True, unique=True, max_length=64)
    password_hash: str
    city: str | None = Field(default=None, max_length=80)
    role: str = Field(default="user", max_length=10)
    consent_training: bool = False
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    last_login_at: datetime | None = None


class RefreshToken(SQLModel, table=True):
    """Jetons de rafraîchissement (rotation + détection de réutilisation par famille)."""

    __tablename__ = "jeton_rafraichissement"
    jti: str = Field(primary_key=True, max_length=64)
    user_id: int = Field(foreign_key="utilisateur.id", index=True)
    family: str = Field(index=True, max_length=64)
    expires_at: datetime
    used_at: datetime | None = None
    revoked: bool = False


# ------------------------------------------------------------------ catalogue & offres
class Category(SQLModel, table=True):
    __tablename__ = "categorie"
    id: str = Field(primary_key=True, max_length=40)
    label: str


class Manufacturer(SQLModel, table=True):
    __tablename__ = "fabricant"
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)


class Component(SQLModel, table=True):
    """Composant du catalogue (cartes incluses, catégorie « carte »)."""

    __tablename__ = "composant"
    id: str = Field(primary_key=True, max_length=60)
    name: str
    category_id: str = Field(foreign_key="categorie.id", index=True)
    manufacturer_id: int | None = Field(default=None, foreign_key="fabricant.id")
    mpn: str | None = Field(default=None, index=True, max_length=80)
    description: str = ""
    supply_min_v: float | None = None
    supply_max_v: float | None = None
    interfaces: str = ""  # vocabulaire contrôlé, séparé par des virgules (C3)
    package: str | None = None
    datasheet_url: str | None = None
    reference_price_eur: float | None = None
    source: str = "catalogue"  # catalogue | lcsc | digikey | fritzing…
    updated_at: datetime = Field(default_factory=utcnow)


class Library(SQLModel, table=True):
    """Bibliothèque Arduino (library_index.json + GitHub)."""

    __tablename__ = "bibliotheque"
    name: str = Field(primary_key=True, max_length=120)
    latest_version: str | None = None
    architectures: str = ""
    includes: str = ""
    repository: str | None = None
    stars: int | None = None


class ComponentLibrary(SQLModel, table=True):
    """Association UTILISE (composant <-> bibliothèque)."""

    __tablename__ = "utilise"
    component_id: str = Field(foreign_key="composant.id", primary_key=True)
    library_name: str = Field(foreign_key="bibliotheque.name", primary_key=True)


class Supplier(SQLModel, table=True):
    __tablename__ = "fournisseur"
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    url: str = ""
    country: str = "FR"
    collection_method: str = "api"  # api | scraping | fichier


class Offer(SQLModel, table=True):
    """Offre datée d'un fournisseur pour un composant (prix normalisé en EUR)."""

    __tablename__ = "offre"
    id: int | None = Field(default=None, primary_key=True)
    component_id: str = Field(foreign_key="composant.id", index=True)
    supplier_id: int = Field(foreign_key="fournisseur.id", index=True)
    sku: str | None = None
    unit_price_eur: float
    price_original: float | None = None
    currency_original: str = "EUR"
    stock: int | None = None
    url: str = ""
    collected_at: datetime = Field(default_factory=utcnow)


# ------------------------------------------------------------------ inventaire & vision
class InventoryItem(SQLModel, table=True):
    __tablename__ = "article_inventaire"
    __table_args__ = (UniqueConstraint("user_id", "component_id", "location"),)
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="utilisateur.id", index=True)
    component_id: str = Field(foreign_key="composant.id")
    quantity: int = Field(default=1, ge=0)
    location: str = Field(default="", max_length=80)
    note: str = Field(default="", max_length=200)
    updated_at: datetime = Field(default_factory=utcnow)


class Photo(SQLModel, table=True):
    """Métadonnées d'une photo d'inventaire (l'image est supprimée après traitement, cf. RGPD)."""

    __tablename__ = "photo"
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="utilisateur.id", index=True)
    sha256: str = Field(max_length=64)
    width: int
    height: int
    model_version: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    delete_after: date | None = None


class Feedback(SQLModel, table=True):
    """Retour utilisateur sur une détection (alimente le monitoring du modèle, C11)."""

    __tablename__ = "retour_detection"
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="utilisateur.id", index=True)
    photo_id: int | None = Field(default=None, foreign_key="photo.id")
    predicted_component_id: str | None = None
    corrected_component_id: str | None = None
    kind: str = Field(max_length=20)  # correct | wrong_label | false_positive | missed
    confidence: float | None = None
    source: str = "yolo"  # yolo | vlm
    model_version: str = ""
    created_at: datetime = Field(default_factory=utcnow)


# ------------------------------------------------------------------ projets
class Project(SQLModel, table=True):
    __tablename__ = "projet"
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="utilisateur.id", index=True)
    title: str = Field(max_length=120)
    board_id: str = Field(foreign_key="composant.id")
    template_id: str | None = None
    spec_json: str
    created_at: datetime = Field(default_factory=utcnow)


class IngestionRun(SQLModel, table=True):
    """Trace des exécutions du pipeline E1 (et de la purge RGPD)."""

    __tablename__ = "execution_collecte"
    id: int | None = Field(default=None, primary_key=True)
    flow: str
    source: str
    status: str = "running"
    rows_in: int = 0
    rows_out: int = 0
    rows_rejected: int = 0
    message: str = ""
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None


# ------------------------------------------------------------------ moteur
@lru_cache(maxsize=4)
def get_engine(url: str | None = None) -> Engine:
    url = url or get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


def init_db(engine: Engine | None = None) -> None:
    SQLModel.metadata.create_all(engine or get_engine())


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
