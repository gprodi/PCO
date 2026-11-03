"""Modèles SQLModel et session de base de données."""

from collections.abc import Iterator
from datetime import UTC, datetime

from sqlalchemy.engine import Engine
from sqlmodel import Field, Session, SQLModel, create_engine

from app.config import get_settings


def utcnow() -> datetime:
    """Heure UTC avec fuseau (SQLModel refuse les dates « naïves » depuis la version 0.0.48)."""
    return datetime.now(UTC)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=254)
    password_hash: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow)


class RefreshToken(SQLModel, table=True):
    """Jeton de rafraîchissement émis ; ``family`` relie les jetons d'une même chaîne de rotation."""

    jti: str = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    family: str = Field(index=True)
    expires_at: datetime
    revoked: bool = False


_engine: Engine | None = None


def engine() -> Engine:
    global _engine
    if _engine is None:
        url = get_settings().database_url
        args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, connect_args=args)
    return _engine


def init_db() -> None:
    SQLModel.metadata.create_all(engine())


def get_session() -> Iterator[Session]:
    with Session(engine()) as session:
        yield session
