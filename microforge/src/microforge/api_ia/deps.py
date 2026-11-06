"""Dépendances d'api_ia : vérification des jetons (clé publique seule), services partagés."""

from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass
from functools import lru_cache

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from llm_gateway import Gateway
from loguru import logger

from microforge.common.security import decode_token
from microforge.common.settings import get_settings
from microforge.copilot import Copilot, make_copilot
from microforge.core.builder import ProjectBuilder
from microforge.core.generator import ProjectGenerator
from microforge.vision import InventoryScanner
from microforge.vision.detector import load_detector

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{get_settings().api_data_url}/v1/auth/token")


@dataclass
class Principal:
    user_id: int
    role: str


@lru_cache(maxsize=1)
def public_key() -> str:
    """Clé publique RS256 : depuis l'environnement, sinon récupérée auprès d'api_data."""
    settings = get_settings()
    if settings.jwt_public_key:
        return settings.jwt_public_key.replace("\\n", "\n")
    url = f"{settings.api_data_url}/v1/auth/public-key"
    logger.info("Récupération de la clé publique sur {}", url)
    resp = httpx.get(url, timeout=10)
    resp.raise_for_status()
    return resp.text


#: Relecture de la clé publique d'api_data au plus une fois par période (secondes).
KEY_REFRESH_SECONDS = 30.0
_last_key_refresh = 0.0


def _decode_access(token: str) -> dict:
    """Vérifie un jeton d'accès.

    Sans clé publique dans l'environnement, la clé vient d'api_data. En développement, api_data
    génère des clés éphémères à chaque démarrage : après un redémarrage (``docker compose restart
    api_data``), l'ancienne clé gardée en cache rejetait tous les jetons (401) jusqu'au redémarrage
    d'api_ia. Sur une signature invalide, la clé est donc relue une fois (au plus toutes les 30 s).
    """
    global _last_key_refresh
    try:
        return decode_token(token, public_key(), "access")
    except jwt.InvalidSignatureError:
        now = time.monotonic()
        if get_settings().jwt_public_key or now - _last_key_refresh < KEY_REFRESH_SECONDS:
            raise
        _last_key_refresh = now
        logger.info("Signature inconnue : relecture de la clé publique d'api_data")
        public_key.cache_clear()
        return decode_token(token, public_key(), "access")


def current_principal(token: str = Depends(oauth2_scheme)) -> Principal:
    try:
        claims = _decode_access(token)
    except (jwt.PyJWTError, httpx.HTTPError) as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Jeton invalide", headers={"WWW-Authenticate": "Bearer"}
        ) from exc
    return Principal(user_id=int(claims["sub"]), role=claims.get("role", "user"))


def user_key(request: Request) -> str:
    """Clé de limitation de débit : identifiant utilisateur si authentifié, sinon IP."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        with contextlib.suppress(jwt.PyJWTError, httpx.HTTPError, KeyError):
            return "user:" + _decode_access(auth[7:])["sub"]
    return "ip:" + (request.client.host if request.client else "inconnu")


@dataclass
class Services:
    gateway: Gateway
    scanner: InventoryScanner
    builder: ProjectBuilder
    generator: ProjectGenerator
    copilot: Copilot


def _copilot(gateway: Gateway, builder: ProjectBuilder) -> Copilot:
    """pgvector si configuré ; base injoignable → index mémoire (le reste d'api_ia continue)."""
    settings = get_settings()
    try:
        return make_copilot(
            gateway, settings.copilot_vector_url, settings.copilot_min_score, builder.catalog
        )
    except Exception as exc:  # pilote absent, base arrêtée, extension manquante…
        logger.error(
            "Copilote : pgvector indisponible ({}), index en mémoire", exc.__class__.__name__
        )
        return make_copilot(gateway, None, settings.copilot_min_score, builder.catalog)


@lru_cache(maxsize=1)
def services() -> Services:
    settings = get_settings()
    gateway = Gateway.from_env()
    detector = load_detector(settings.yolo_weights, settings.mlflow_model_uri)
    builder = ProjectBuilder()
    return Services(
        gateway=gateway,
        scanner=InventoryScanner(gateway, detector, builder.catalog),
        builder=builder,
        generator=ProjectGenerator(gateway, builder.catalog),
        copilot=_copilot(gateway, builder),
    )
