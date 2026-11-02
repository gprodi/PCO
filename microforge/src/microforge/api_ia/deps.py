"""Dépendances d'api_ia : vérification des jetons (clé publique seule), services partagés."""

from __future__ import annotations

import contextlib
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


def current_principal(token: str = Depends(oauth2_scheme)) -> Principal:
    try:
        claims = decode_token(token, public_key(), "access")
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
            return "user:" + decode_token(auth[7:], public_key(), "access")["sub"]
    return "ip:" + (request.client.host if request.client else "inconnu")


@dataclass
class Services:
    gateway: Gateway
    scanner: InventoryScanner
    builder: ProjectBuilder
    generator: ProjectGenerator


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
    )
