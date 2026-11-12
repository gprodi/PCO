"""API d'IA : comptes (jetons de rafraîchissement à rotation) et ``POST /chat`` qui pilote le graphe.

Seul composant à parler à l'API de données (réseau privé) et aux modèles ; l'interface ne parle qu'à elle.
"""

import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from typing import Annotated

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from prometheus_client import make_asgi_app
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlmodel import Session, select

from api_ia import comptes
from api_ia.metriques import LATENCE, QUESTIONS, REQUETES
from api_ia.services import Services, construire
from commun.config import Settings, get_settings
from commun.logs import configurer

limiteur = Limiter(key_func=get_remote_address)
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/jeton")
REFUS = HTTPException(status.HTTP_401_UNAUTHORIZED, "Identifiants invalides", headers={"WWW-Authenticate": "Bearer"})
SessionDep = Annotated[Session, Depends(comptes.session)]


class InscriptionIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    mot_de_passe: str = Field(min_length=12, max_length=128)


class JetonsOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 - type de jeton OAuth2, pas un secret


class RafraichirIn(BaseModel):
    refresh_token: str


class ChatIn(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    session: str | None = Field(default=None, max_length=64)


class ChatOut(BaseModel):
    reponse: str
    sources: list[dict]
    etapes: list[str]
    verdict: str
    fournisseur: str
    similaires: list[dict] = Field(default_factory=list)


def compte_courant(jeton: Annotated[str, Depends(oauth2)], s: SessionDep) -> comptes.Compte:
    try:
        charge = comptes.decoder(jeton, "acces")
    except jwt.PyJWTError:
        raise REFUS from None
    compte = s.get(comptes.Compte, int(charge["sub"]))
    if compte is None or not compte.actif:
        raise REFUS
    return compte


def creer_app(fabrique: Callable[[Settings], Services] = construire) -> FastAPI:
    @asynccontextmanager
    async def cycle_de_vie(app: FastAPI) -> AsyncIterator[None]:
        reglages = get_settings()
        configurer(json=reglages.log_json)
        comptes._cle()  # échoue au démarrage si APP_SECRET_KEY manque
        comptes.creer_tables()
        app.state.services = fabrique(reglages)
        await run_in_threadpool(app.state.services.charger)
        yield

    app = FastAPI(title="API d'IA", version="0.1.0", lifespan=cycle_de_vie)
    app.state.limiter = limiteur
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.mount("/metrics", make_asgi_app())

    @app.middleware("http")
    async def entetes_et_mesures(request: Request, call_next):
        debut = time.perf_counter()
        reponse = await call_next(request)
        route = request.scope.get("route")
        chemin = getattr(route, "path", "autre")
        REQUETES.labels(chemin, request.method, str(reponse.status_code)).inc()
        LATENCE.labels(chemin).observe(time.perf_counter() - debut)
        reponse.headers["X-Content-Type-Options"] = "nosniff"
        reponse.headers["X-Frame-Options"] = "DENY"
        reponse.headers["Referrer-Policy"] = "no-referrer"
        reponse.headers["Cache-Control"] = "no-store"
        return reponse

    @app.get("/health")
    def sante(request: Request) -> dict:
        return {"statut": "ok", "index_pret": request.app.state.services.pret}

    @app.post("/auth/inscription", status_code=status.HTTP_201_CREATED)
    def inscription(corps: InscriptionIn, s: SessionDep) -> dict:
        email = corps.email.lower()
        if s.exec(select(comptes.Compte).where(comptes.Compte.email == email)).first():
            raise HTTPException(status.HTTP_409_CONFLICT, "Compte déjà existant")
        compte = comptes.Compte(email=email, hache=comptes.hacher(corps.mot_de_passe))
        s.add(compte)
        s.commit()
        return {"id": compte.id, "email": email}

    @app.post("/auth/jeton", response_model=JetonsOut)
    @limiteur.limit(lambda: get_settings().login_rate)
    def connexion(request: Request, form: Annotated[OAuth2PasswordRequestForm, Depends()], s: SessionDep) -> JetonsOut:
        compte = s.exec(select(comptes.Compte).where(comptes.Compte.email == form.username.lower())).first()
        valide = comptes.verifier(compte.hache if compte else comptes.HACHE_FACTICE, form.password)
        if compte is None or not valide or not compte.actif:
            raise REFUS
        acces, rafraichissement = comptes.emettre(s, compte.id)
        return JetonsOut(access_token=acces, refresh_token=rafraichissement)

    @app.post("/auth/rafraichir", response_model=JetonsOut)
    def rafraichir(corps: RafraichirIn, s: SessionDep) -> JetonsOut:
        try:
            charge = comptes.decoder(corps.refresh_token, "rafraichissement")
        except jwt.PyJWTError:
            raise REFUS from None
        stocke = s.get(comptes.JetonRafraichissement, charge["jti"])
        if stocke is None:
            raise REFUS
        if stocke.revoque:
            comptes.revoquer_famille(s, stocke.famille)  # rejeu : toute la chaîne tombe
            raise REFUS
        stocke.revoque = True
        s.add(stocke)
        s.commit()
        acces, rafraichissement = comptes.emettre(s, stocke.compte_id, stocke.famille)
        return JetonsOut(access_token=acces, refresh_token=rafraichissement)

    @app.post("/auth/deconnexion", status_code=status.HTTP_204_NO_CONTENT)
    def deconnexion(corps: RafraichirIn, s: SessionDep) -> Response:
        with suppress(jwt.PyJWTError):  # jeton illisible : rien à révoquer
            comptes.revoquer_famille(s, comptes.decoder(corps.refresh_token, "rafraichissement")["fam"])
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.delete("/auth/moi", status_code=status.HTTP_204_NO_CONTENT)
    def effacer(compte: Annotated[comptes.Compte, Depends(compte_courant)], s: SessionDep) -> Response:
        """Droit à l'effacement (RGPD) : le compte et ses jetons sont supprimés."""
        for jeton in s.exec(
            select(comptes.JetonRafraichissement).where(comptes.JetonRafraichissement.compte_id == compte.id)
        ):
            s.delete(jeton)
        s.delete(s.get(comptes.Compte, compte.id))
        s.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/chat", response_model=ChatOut)
    @limiteur.limit(lambda: get_settings().chat_rate)
    def chat(request: Request, corps: ChatIn, compte: Annotated[comptes.Compte, Depends(compte_courant)]) -> ChatOut:
        services: Services = request.app.state.services
        if not services.pret and not services.charger():
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Base de connaissances pas encore chargée")
        reponse = services.assistant.repondre(corps.question, corps.session, str(compte.id))
        QUESTIONS.labels(reponse.verdict, reponse.fournisseur).inc()
        return ChatOut(**reponse.__dict__)

    return app


app = creer_app()
