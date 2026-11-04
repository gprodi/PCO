"""Hachage des mots de passe (Argon2id) et jetons JWT."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import get_settings

ALGORITHM = "HS256"
_hasher = PasswordHasher()  # Argon2id, paramètres par défaut recommandés (RFC 9106)
#: Haché factice : vérifié quand le compte n'existe pas, pour que la réponse prenne le même temps.
DUMMY_HASH = _hasher.hash(secrets.token_hex(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: int) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {"sub": str(user_id), "type": "access", "iat": now, "exp": now + timedelta(minutes=s.access_minutes)}
    return jwt.encode(payload, s.secret_key, algorithm=ALGORITHM)


def create_refresh_token(user_id: int, family: str | None = None) -> tuple[str, str, str, datetime]:
    """Renvoie (jeton, jti, famille, expiration)."""
    s = get_settings()
    now = datetime.now(UTC)
    jti, family = uuid.uuid4().hex, family or uuid.uuid4().hex
    expires = now + timedelta(days=s.refresh_days)
    payload = {"sub": str(user_id), "type": "refresh", "jti": jti, "fam": family, "iat": now, "exp": expires}
    return jwt.encode(payload, s.secret_key, algorithm=ALGORITHM), jti, family, expires


def decode(token: str, expected_type: str) -> dict:
    """Vérifie signature, expiration et type ; lève ``jwt.PyJWTError`` sinon."""
    payload = jwt.decode(
        token, get_settings().secret_key, algorithms=[ALGORITHM], options={"require": ["exp", "sub", "type"]}
    )
    if payload["type"] != expected_type:
        raise jwt.InvalidTokenError("type de jeton inattendu")
    return payload
