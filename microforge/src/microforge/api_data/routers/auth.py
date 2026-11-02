"""Authentification : inscription, jeton (OAuth2 password), rafraîchissement avec rotation, déconnexion."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from fastapi.security import OAuth2PasswordRequestForm
from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from microforge.api_data.db import RefreshToken, User, get_session, utcnow
from microforge.api_data.deps import UNAUTHORIZED
from microforge.api_data.limiter import limiter
from microforge.api_data.schemas import RefreshIn, RegisterIn, TokenPair, UserOut
from microforge.common.security import (
    blind_index,
    create_access_token,
    create_refresh_token,
    decode_token,
    encrypt,
    hash_password,
    signing_keys,
    verify_password,
)
from microforge.common.settings import get_settings

router = APIRouter(prefix="/v1/auth", tags=["auth"])

# Hash factice : temps de réponse constant même si l'utilisateur n'existe pas (anti-énumération).
_DUMMY_HASH = hash_password("pas-un-vrai-mot-de-passe-0")


def _issue(session: Session, user: User, family: str | None = None) -> TokenPair:
    keys = signing_keys()
    family = family or uuid.uuid4().hex
    refresh, jti, exp = create_refresh_token(user.id, family, keys)  # type: ignore[arg-type]
    session.add(RefreshToken(jti=jti, user_id=user.id, family=family, expires_at=exp))  # type: ignore[arg-type]
    session.commit()
    return TokenPair(
        access_token=create_access_token(user.id, user.role, keys),  # type: ignore[arg-type]
        refresh_token=refresh,
        expires_in=get_settings().access_minutes * 60,
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(request: Request, body: RegisterIn, session: Session = Depends(get_session)) -> User:
    user = User(
        username=body.username,
        email_encrypted=encrypt(body.email),
        email_index=blind_index(body.email),
        password_hash=hash_password(body.password),
        city=body.city,
        consent_training=body.consent_training,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Pseudo ou e-mail déjà utilisé") from exc
    session.refresh(user)
    logger.info("Nouvel utilisateur id={}", user.id)
    return user


@router.post("/token", response_model=TokenPair)
@limiter.limit(lambda: get_settings().rate_limit_token)
def token(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
) -> TokenPair:
    """Connexion par pseudo **ou** e-mail."""
    ident = form.username.strip()
    user = session.exec(
        select(User).where((User.username == ident) | (User.email_index == blind_index(ident)))
    ).first()
    if user is None:
        verify_password(form.password, _DUMMY_HASH)
        logger.info("Échec de connexion (identifiant inconnu)")
        raise UNAUTHORIZED
    if not verify_password(form.password, user.password_hash) or not user.is_active:
        logger.info("Échec de connexion user={}", user.id)
        raise UNAUTHORIZED
    user.last_login_at = utcnow()
    session.add(user)
    return _issue(session, user)


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshIn, session: Session = Depends(get_session)) -> TokenPair:
    """Rotation : l'ancien refresh token est consommé ; sa réutilisation révoque toute la famille."""
    try:
        claims = decode_token(body.refresh_token, signing_keys().public_pem, "refresh")
    except jwt.PyJWTError as exc:
        raise UNAUTHORIZED from exc
    stored = session.get(RefreshToken, claims["jti"])
    if stored is None:
        raise UNAUTHORIZED
    if stored.revoked or stored.used_at is not None:
        # Réutilisation d'un jeton déjà consommé : vol probable -> on révoque la famille.
        for tok in session.exec(select(RefreshToken).where(RefreshToken.family == stored.family)):
            tok.revoked = True
            session.add(tok)
        session.commit()
        logger.warning("Réutilisation de refresh token détectée user={}", stored.user_id)
        raise UNAUTHORIZED
    expires = (
        stored.expires_at if stored.expires_at.tzinfo else stored.expires_at.replace(tzinfo=UTC)
    )
    if expires < datetime.now(UTC):
        raise UNAUTHORIZED
    stored.used_at = utcnow()
    session.add(stored)
    user = session.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise UNAUTHORIZED
    return _issue(session, user, family=stored.family)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshIn, session: Session = Depends(get_session)) -> None:
    """Révoque toute la famille du refresh token (déconnexion de la session)."""
    try:
        claims = decode_token(body.refresh_token, signing_keys().public_pem, "refresh")
    except jwt.PyJWTError as exc:
        raise UNAUTHORIZED from exc
    for tok in session.exec(select(RefreshToken).where(RefreshToken.family == claims["fam"])):
        tok.revoked = True
        session.add(tok)
    session.commit()


@router.get("/public-key", response_class=PlainTextResponse)
def public_key() -> str:
    """Clé publique RS256 (PEM) : permet à api_ia de vérifier les jetons sans pouvoir en signer."""
    return signing_keys().public_pem
