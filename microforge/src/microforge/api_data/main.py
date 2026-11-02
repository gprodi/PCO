"""Application FastAPI « api_data » (port 8000)."""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from prometheus_client import Gauge
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlmodel import Session, func, select

from microforge.api_data.catalog_sync import sync_catalog
from microforge.api_data.db import Feedback, get_engine, init_db
from microforge.api_data.limiter import limiter
from microforge.api_data.routers import admin, auth, catalog, inventory, projects, users
from microforge.common.security import signing_keys
from microforge.common.settings import get_settings, setup_logging

CORRECTION_RATE = Gauge(
    "mf_detection_correction_rate",
    "Part des détections corrigées par les utilisateurs (7 derniers jours)",
    ["source"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging("api_data", settings)
    signing_keys()  # fail-closed : lève une erreur si les clés manquent hors dev
    init_db()
    with Session(get_engine()) as session:
        n = sync_catalog(session)
    logger.info("api_data prête ({} composants au catalogue)", n)
    yield


def refresh_business_metrics() -> None:
    """Calcule les métriques métier exposées sur /metrics (taux de corrections — C11)."""
    from datetime import UTC, datetime, timedelta

    since = datetime.now(UTC) - timedelta(days=7)
    with Session(get_engine()) as session:
        rows = session.exec(
            select(Feedback.source, Feedback.kind, func.count())
            .where(Feedback.created_at >= since)
            .group_by(Feedback.source, Feedback.kind)
        ).all()
    totals: dict[str, list[int]] = {}
    for source, kind, n in rows:
        t = totals.setdefault(source, [0, 0])
        t[0] += n
        if kind != "correct":
            t[1] += n
    for source, (total, wrong) in totals.items():
        CORRECTION_RATE.labels(source=source).set(wrong / total if total else 0)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="MicroForge — API données",
        version="0.1.0",
        description=(
            "Mise à disposition du catalogue de composants, des offres fournisseurs et des données "
            "utilisateur (inventaire, projets). Authentification OAuth2 (password) + JWT RS256 "
            "(access 15 min, refresh 7 j avec rotation)."
        ),
        lifespan=lifespan,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        start = time.perf_counter()
        with logger.contextualize(request_id=request_id):
            response = await call_next(request)
            elapsed = (time.perf_counter() - start) * 1000
            logger.info(
                "{} {} -> {} ({:.0f} ms)",
                request.method,
                request.url.path,
                response.status_code,
                elapsed,
            )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    for router in (
        auth.router,
        users.router,
        catalog.router,
        inventory.router,
        projects.router,
        admin.router,
    ):
        app.include_router(router)

    @app.get("/health", tags=["supervision"])
    def health() -> dict[str, str]:
        with Session(get_engine()) as session:
            session.exec(select(1)).one()
        return {"status": "ok", "service": "api_data"}

    instrumentator = Instrumentator(excluded_handlers=["/metrics", "/health"]).instrument(app)

    @app.middleware("http")
    async def metrics_refresh(request: Request, call_next):
        if request.url.path == "/metrics":
            try:
                refresh_business_metrics()
            except Exception as exc:  # la supervision ne doit jamais casser /metrics
                logger.warning("Métriques métier indisponibles : {}", exc)
        return await call_next(request)

    instrumentator.expose(app, include_in_schema=False)
    return app


app = create_app()
