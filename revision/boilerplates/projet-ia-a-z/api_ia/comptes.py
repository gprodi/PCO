"""Comptes de l'interface : Argon2id, jeton d'accès court, jeton de rafraîchissement à rotation.

Un jeton de rafraîchissement déjà échangé, présenté une seconde fois, révoque toute sa famille
(vol probable). Données personnelles réduites au minimum : une adresse et un haché.
"""

import secrets
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import Engine
from sqlmodel import Field, Session, SQLModel, create_engine, select

from commun.config import get_settings

ALGORITHME = "HS256"
_hacheur = PasswordHasher()
#: vérifié quand le compte n'existe pas : même durée de réponse
HACHE_FACTICE = _hacheur.hash(secrets.token_hex(16))


def maintenant() -> datetime:
    return datetime.now(UTC)


class Compte(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=254)
    hache: str
    actif: bool = True
    cree_le: datetime = Field(default_factory=maintenant)


class JetonRafraichissement(SQLModel, table=True):
    __tablename__ = "jeton_rafraichissement"

    jti: str = Field(primary_key=True)
    compte_id: int = Field(foreign_key="compte.id", index=True)
    famille: str = Field(index=True)
    expire_le: datetime
    revoque: bool = False


@lru_cache
def moteur() -> Engine:
    url = get_settings().auth_database_url
    options = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=options, pool_pre_ping=True)


def creer_tables() -> None:
    SQLModel.metadata.create_all(moteur(), tables=[Compte.__table__, JetonRafraichissement.__table__])


def session() -> Iterator[Session]:
    with Session(moteur()) as s:
        yield s


def hacher(mot_de_passe: str) -> str:
    return _hacheur.hash(mot_de_passe)


def verifier(hache: str, mot_de_passe: str) -> bool:
    try:
        return _hacheur.verify(hache, mot_de_passe)
    except (VerificationError, InvalidHashError):
        return False


def _cle() -> str:
    cle = get_settings().secret_key
    if not cle:
        raise RuntimeError("APP_SECRET_KEY manquante (32 caractères au moins)")
    return cle


def jeton_acces(compte_id: int) -> str:
    instant = maintenant()
    duree = timedelta(minutes=get_settings().access_minutes)
    charge = {"sub": str(compte_id), "type": "acces", "iat": instant, "exp": instant + duree}
    return jwt.encode(charge, _cle(), algorithm=ALGORITHME)


def jeton_rafraichissement(compte_id: int, famille: str | None = None) -> tuple[str, str, str, datetime]:
    """Renvoie (jeton, jti, famille, expiration)."""
    instant = maintenant()
    jti, famille = uuid.uuid4().hex, famille or uuid.uuid4().hex
    expire = instant + timedelta(days=get_settings().refresh_days)
    charge = {
        "sub": str(compte_id),
        "type": "rafraichissement",
        "jti": jti,
        "fam": famille,
        "iat": instant,
        "exp": expire,
    }
    return jwt.encode(charge, _cle(), algorithm=ALGORITHME), jti, famille, expire


def decoder(jeton: str, type_attendu: str) -> dict:
    """Signature, expiration et type vérifiés ; lève ``jwt.PyJWTError`` sinon."""
    charge = jwt.decode(jeton, _cle(), algorithms=[ALGORITHME], options={"require": ["exp", "sub", "type"]})
    if charge["type"] != type_attendu:
        raise jwt.InvalidTokenError("type de jeton inattendu")
    return charge


def emettre(s: Session, compte_id: int, famille: str | None = None) -> tuple[str, str]:
    jeton, jti, famille, expire = jeton_rafraichissement(compte_id, famille)
    s.add(JetonRafraichissement(jti=jti, compte_id=compte_id, famille=famille, expire_le=expire))
    s.commit()
    return jeton_acces(compte_id), jeton


def revoquer_famille(s: Session, famille: str) -> None:
    for jeton in s.exec(select(JetonRafraichissement).where(JetonRafraichissement.famille == famille)):
        jeton.revoque = True
        s.add(jeton)
    s.commit()
