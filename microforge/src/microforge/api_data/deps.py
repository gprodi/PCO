"""Dépendances FastAPI : session, utilisateur courant, rôles."""

from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from loguru import logger
from sqlmodel import Session

from microforge.api_data.db import User, get_session
from microforge.common.security import decode_token, signing_keys

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/token")

UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Authentification requise ou jeton invalide",
    headers={"WWW-Authenticate": "Bearer"},
)


def current_user(
    token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)
) -> User:
    try:
        claims = decode_token(token, signing_keys().public_pem, "access")
    except jwt.PyJWTError as exc:
        logger.info("Jeton refusé : {}", type(exc).__name__)
        raise UNAUTHORIZED from exc
    user = session.get(User, int(claims["sub"]))
    if user is None or not user.is_active:
        raise UNAUTHORIZED
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        logger.warning("Accès admin refusé pour l'utilisateur {}", user.id)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux administrateurs")
    return user
