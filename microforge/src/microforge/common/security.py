"""Sécurité : hachage des mots de passe, JWT RS256, chiffrement des données personnelles.

Choix (cf. cours « Sécuriser une API FastAPI ») :

* **argon2** via pwdlib pour les mots de passe ;
* **JWT RS256** : api_data signe avec la clé privée, api_ia vérifie avec la clé publique sans
  pouvoir signer (justification du RS256 vs HS256 : plusieurs services vérifient) ;
* liste blanche d'algorithmes, ``aud``/``iss``/``exp`` obligatoires (pas d'``alg: none``) ;
* **refresh tokens** rotatifs avec détection de réutilisation (famille révoquée) ;
* **Fernet** pour chiffrer l'e-mail + **index aveugle** HMAC pour le retrouver sans le déchiffrer ;
* **fail-closed** : hors développement, l'absence de clé empêche le démarrage.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from loguru import logger
from pwdlib import PasswordHash

from microforge.common.settings import Settings, get_settings

ALGORITHMS = ["RS256"]
_hasher = PasswordHash.recommended()


class SecurityConfigError(RuntimeError):
    """Configuration de sécurité absente ou invalide (démarrage refusé)."""


# ---------------------------------------------------------------------------- mots de passe
def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(password, hashed)
    except Exception:  # hash corrompu
        return False


# ---------------------------------------------------------------------------- clés
@dataclass(frozen=True)
class KeyPair:
    private_pem: str | None
    public_pem: str


def generate_keypair() -> KeyPair:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return KeyPair(private_pem, public_pem)


def _pem(value: str) -> str:
    # Les .env acceptent mal les sauts de ligne : on autorise "\n" littéraux.
    return value.replace("\\n", "\n").strip() + "\n"


@lru_cache(maxsize=1)
def signing_keys() -> KeyPair:
    """Clés de signature de api_data (générées à la volée en développement uniquement)."""
    settings = get_settings()
    if settings.jwt_private_key and settings.jwt_public_key:
        return KeyPair(_pem(settings.jwt_private_key), _pem(settings.jwt_public_key))
    if settings.env != "dev":
        raise SecurityConfigError("MF_JWT_PRIVATE_KEY / MF_JWT_PUBLIC_KEY manquantes (fail-closed)")
    logger.warning("Clés JWT éphémères générées (MF_ENV=dev) : ne pas utiliser en production")
    return generate_keypair()


@lru_cache(maxsize=1)
def fernet() -> Fernet:
    settings = get_settings()
    if settings.fernet_key:
        return Fernet(settings.fernet_key.encode())
    if settings.env != "dev":
        raise SecurityConfigError("MF_FERNET_KEY manquante (fail-closed)")
    # Clé dérivée déterministe en dev pour que les données restent lisibles entre redémarrages.
    digest = hashlib.sha256(f"dev-only-{settings.blind_index_salt}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(value: str) -> str:
    return fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    return fernet().decrypt(token.encode()).decode()


def blind_index(value: str, settings: Settings | None = None) -> str:
    """HMAC-SHA256 normalisé : permet l'unicité et la recherche sans stocker l'e-mail en clair."""
    settings = settings or get_settings()
    return hmac.new(
        settings.blind_index_salt.encode(), value.strip().lower().encode(), hashlib.sha256
    ).hexdigest()


# ---------------------------------------------------------------------------- JWT
def _now() -> datetime:
    return datetime.now(UTC)


def create_access_token(
    user_id: int, role: str, keys: KeyPair, settings: Settings | None = None
) -> str:
    settings = settings or get_settings()
    if not keys.private_pem:
        raise SecurityConfigError("Pas de clé privée : ce service ne peut pas signer")
    now = _now()
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_minutes),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, keys.private_pem, algorithm="RS256")


def create_refresh_token(
    user_id: int, family: str, keys: KeyPair, settings: Settings | None = None
) -> tuple[str, str, datetime]:
    """Renvoie (token, jti, expiration)."""
    settings = settings or get_settings()
    if not keys.private_pem:
        raise SecurityConfigError("Pas de clé privée : ce service ne peut pas signer")
    now = _now()
    jti = uuid.uuid4().hex
    exp = now + timedelta(days=settings.refresh_days)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "fam": family,
        "jti": jti,
        "iat": now,
        "exp": exp,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return jwt.encode(payload, keys.private_pem, algorithm="RS256"), jti, exp


def decode_token(
    token: str, public_pem: str, expected_type: str, settings: Settings | None = None
) -> dict[str, Any]:
    """Vérifie signature, algorithme (liste blanche), audience, émetteur, expiration et type."""
    settings = settings or get_settings()
    claims = jwt.decode(
        token,
        public_pem,
        algorithms=ALGORITHMS,
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "iat", "sub", "iss", "aud", "jti"]},
    )
    if claims.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"type de jeton inattendu : {claims.get('type')}")
    return claims
