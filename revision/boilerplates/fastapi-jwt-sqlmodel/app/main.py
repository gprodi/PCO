"""API : inscription, connexion, rotation des jetons, profil."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlmodel import Session, select

from app.config import get_settings
from app.db import RefreshToken, User, get_session, init_db
from app.security import (
    DUMMY_HASH,
    create_access_token,
    create_refresh_token,
    decode,
    hash_password,
    verify_password,
)

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    get_settings()  # échoue tout de suite si APP_SECRET_KEY manque ou est trop court
    init_db()
    yield


app = FastAPI(title="API sécurisée", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


class RegisterIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    password: str = Field(min_length=12, max_length=128)


class UserOut(BaseModel):
    id: int
    email: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


SessionDep = Annotated[Session, Depends(get_session)]
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/token")
CREDENTIALS = HTTPException(
    status.HTTP_401_UNAUTHORIZED, "Identifiants invalides", headers={"WWW-Authenticate": "Bearer"}
)


def current_user(token: Annotated[str, Depends(oauth2)], session: SessionDep) -> User:
    try:
        payload = decode(token, "access")
    except jwt.PyJWTError:
        raise CREDENTIALS from None
    user = session.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise CREDENTIALS
    return user


def _issue(session: Session, user_id: int, family: str | None = None) -> TokenOut:
    token, jti, family, expires = create_refresh_token(user_id, family)
    session.add(RefreshToken(jti=jti, user_id=user_id, family=family, expires_at=expires))
    session.commit()
    return TokenOut(access_token=create_access_token(user_id), refresh_token=token)


def _revoke_family(session: Session, family: str) -> None:
    for token in session.exec(select(RefreshToken).where(RefreshToken.family == family)):
        token.revoked = True
        session.add(token)
    session.commit()


@app.post("/auth/register", status_code=status.HTTP_201_CREATED, response_model=UserOut)
def register(body: RegisterIn, session: SessionDep) -> UserOut:
    email = body.email.lower()
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Compte déjà existant")
    user = User(email=email, password_hash=hash_password(body.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserOut(id=user.id, email=user.email)


@app.post("/auth/token", response_model=TokenOut)
@limiter.limit(lambda: get_settings().login_rate)
def login(
    request: Request, form: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep
) -> TokenOut:
    user = session.exec(select(User).where(User.email == form.username.lower())).first()
    # Toujours vérifier un haché : même durée de réponse que le compte existe ou non.
    valid = verify_password(user.password_hash if user else DUMMY_HASH, form.password)
    if user is None or not valid or not user.is_active:
        raise CREDENTIALS
    return _issue(session, user.id)


@app.post("/auth/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, session: SessionDep) -> TokenOut:
    try:
        payload = decode(body.refresh_token, "refresh")
    except jwt.PyJWTError:
        raise CREDENTIALS from None
    stored = session.get(RefreshToken, payload["jti"])
    if stored is None:
        raise CREDENTIALS
    if stored.revoked:
        # Jeton déjà échangé présenté une seconde fois : vol probable, toute la chaîne est révoquée.
        _revoke_family(session, stored.family)
        raise CREDENTIALS
    stored.revoked = True
    session.add(stored)
    session.commit()
    return _issue(session, stored.user_id, stored.family)


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshIn, session: SessionDep) -> Response:
    try:
        payload = decode(body.refresh_token, "refresh")
    except jwt.PyJWTError:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    _revoke_family(session, payload["fam"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/me", response_model=UserOut)
def me(user: Annotated[User, Depends(current_user)]) -> UserOut:
    return UserOut(id=user.id, email=user.email)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
