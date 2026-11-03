"""Application FastAPI « api_ia » (port 8001)."""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from llm_gateway import LLMError
from loguru import logger
from prometheus_client import Gauge
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from microforge.api_ia.deps import Principal, current_principal, services, user_key
from microforge.api_ia.schemas import (
    BuildIn,
    BuildOut,
    CopilotIn,
    ExploreIn,
    GoalIn,
    IdeasIn,
    InventoryIn,
)
from microforge.common.settings import get_settings, setup_logging
from microforge.copilot import CopilotAnswer
from microforge.core.allocator import AllocationError
from microforge.core.ideas import explore, inspiration
from microforge.core.models import BuildResult, ProjectSpec
from microforge.core.suggest import suggest_projects
from microforge.vision import ScanResult
from microforge.vision.preprocess import InvalidImageError

limiter = Limiter(key_func=user_key)
LLM_CALLS = Gauge("mf_llm_calls", "Appels LLM par fournisseur / échecs / fallbacks", ["kind"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging("api_ia")
    svc = services()
    logger.info(
        "api_ia prête : détecteur={}, chaîne LLM={}, profil={}",
        svc.scanner.model_version,
        [p.name for p in svc.gateway.providers],
        svc.gateway.profile.name,
    )
    yield


def _build_out(result: BuildResult) -> BuildOut:
    svc = services()
    return BuildOut(
        spec=result.spec,
        ok=result.ok,
        issues=[i.model_dump(mode="json") for i in result.issues],
        assignments=[a.model_dump(mode="json") for a in result.assignments],
        added_parts=[p.model_dump(mode="json") for p in result.added_parts],
        bom=[b.model_dump(mode="json") for b in result.bom],
        libraries=result.libraries,
        files=svc.builder.files(result),
    )


def _spec(body: BuildIn) -> ProjectSpec:
    svc = services()
    if body.spec is not None:
        return body.spec
    if body.template_id and body.template_id in svc.builder.catalog.templates:
        return svc.builder.spec_from_template(body.template_id, body.board or "arduino-uno")
    raise HTTPException(422, "Fournir spec, ou template_id (+ board)")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="MicroForge — API IA",
        version="0.1.0",
        description=(
            "Expose le modèle de vision (inventaire photo), le moteur de suggestions et la génération "
            "de projets (câblage, firmware, Wokwi, KiCad). Jetons émis par api_data (RS256)."
        ),
        lifespan=lifespan,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_list,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        start = time.perf_counter()
        with logger.contextualize(request_id=request_id):
            response = await call_next(request)
            logger.info(
                "{} {} -> {} ({:.0f} ms)",
                request.method,
                request.url.path,
                response.status_code,
                (time.perf_counter() - start) * 1000,
            )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health", tags=["supervision"])
    def health() -> dict:
        svc = services()
        return {
            "status": "ok",
            "service": "api_ia",
            "detector": svc.scanner.model_version,
            "llm_chain": [p.name for p in svc.gateway.providers],
        }

    @app.get("/v1/models/current", tags=["modèle"])
    def current_model(_p: Principal = Depends(current_principal)) -> dict:
        svc = services()
        return {
            "detector": svc.scanner.model_version,
            "llm_chain": [p.name for p in svc.gateway.providers],
            "profile": svc.gateway.profile.name,
            "vision_model": svc.gateway.profile.model_for("ollama", "vision"),
            "llm_stats": dict(svc.gateway.stats),
            "copilot_index": svc.copilot.backend,
        }

    @app.post("/v1/copilot/ask", response_model=CopilotAnswer, tags=["copilote"])
    @limiter.limit(lambda: get_settings().rate_limit_copilot)
    def copilot_ask(
        request: Request, body: CopilotIn, p: Principal = Depends(current_principal)
    ) -> CopilotAnswer:
        """Question libre sur le matériel : réponse citée [n] à partir du catalogue (RAG).

        « Je ne sais pas » sous le seuil de similarité ; passages bruts si aucun modèle de langage
        n'est joignable. La question n'est pas journalisée (seulement le mode et le nombre de sources).
        """
        try:
            answer = services().copilot.ask(body.question, body.inventory)
        except LLMError as exc:  # pas de modèle d'embeddings : recherche impossible
            raise HTTPException(503, "Copilote indisponible : aucun modèle d'embeddings") from exc
        logger.info(
            "Copilote user={} mode={} sources={}", p.user_id, answer.mode, len(answer.sources)
        )
        return answer

    @app.post("/v1/vision/scan", response_model=ScanResult, tags=["vision"])
    @limiter.limit(lambda: get_settings().rate_limit_vision)
    async def scan(
        request: Request, image: UploadFile = File(...), p: Principal = Depends(current_principal)
    ) -> ScanResult:
        """Analyse une photo de stock (JPEG/PNG/WEBP ≤ 8 Mo, métadonnées supprimées)."""
        max_bytes = settings.max_upload_mb * 1024 * 1024
        data = await image.read(max_bytes + 1)
        try:
            result = services().scanner.scan(data, max_bytes=max_bytes)
        except InvalidImageError as exc:
            raise HTTPException(422, str(exc)) from exc
        logger.info(
            "Scan user={} mode={} items={} inconnus={}",
            p.user_id,
            result.mode,
            len(result.items),
            len(result.unknown),
        )
        return result

    @app.post("/v1/builds/suggest", tags=["projets"])
    def suggest(body: InventoryIn, _p: Principal = Depends(current_principal)) -> list[dict]:
        return [
            s.to_dict()
            for s in suggest_projects(
                body.inventory, services().builder.catalog, body.limit, body.max_missing
            )
        ]

    @app.post("/v1/builds/generate", response_model=BuildOut, tags=["projets"])
    def generate(body: BuildIn, _p: Principal = Depends(current_principal)) -> BuildOut:
        try:
            return _build_out(services().builder.build(_spec(body)))
        except (AllocationError, KeyError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/v1/builds/bundle", tags=["projets"], response_class=Response)
    def bundle(body: BuildIn, _p: Principal = Depends(current_principal)) -> Response:
        svc = services()
        try:
            result = svc.builder.build(_spec(body))
        except (AllocationError, KeyError) as exc:
            raise HTTPException(422, str(exc)) from exc
        return Response(
            svc.builder.bundle(result),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="microforge-projet.zip"'},
        )

    @app.post("/v1/builds/from-goal", response_model=BuildOut, tags=["projets"])
    @limiter.limit("20/hour")
    def from_goal(
        request: Request, body: GoalIn, _p: Principal = Depends(current_principal)
    ) -> BuildOut:
        """« Je veux construire… » : le LLM choisit les composants, le cœur déterministe câble."""
        svc = services()
        spec = svc.generator.from_goal(body.goal, body.inventory, body.board, body.components)
        return _build_out(svc.builder.build(spec))

    @app.post("/v1/ideas/explore", tags=["projets"])
    def explore_ideas(body: ExploreIn, _p: Principal = Depends(current_principal)) -> list[dict]:
        """Idées de projets par thème (plantes, intérieur, extérieur, sécurité…), annotées avec le stock."""
        return explore(body.inventory, services().builder.catalog)

    @app.get("/v1/ideas/inspiration", tags=["projets"])
    def ideas_inspiration(_p: Principal = Depends(current_principal)) -> dict:
        """Parcours de progression (1re LED -> robot), vitrine de vrais projets open source, chiffres clés."""
        return inspiration(services().builder.catalog)

    @app.post("/v1/builds/ideas", tags=["projets"])
    @limiter.limit("20/hour")
    def ideas(
        request: Request, body: IdeasIn, _p: Principal = Depends(current_principal)
    ) -> list[dict]:
        svc = services()
        out = []
        for spec in svc.generator.ideas_from_inventory(body.inventory, body.n):
            result = svc.builder.build(spec)
            out.append(
                {
                    "spec": spec.model_dump(),
                    "ok": result.ok,
                    "issues": [i.model_dump(mode="json") for i in result.issues],
                }
            )
        return out

    instrumentator = Instrumentator(excluded_handlers=["/metrics", "/health"]).instrument(app)

    @app.middleware("http")
    async def llm_metrics(request: Request, call_next):
        if request.url.path == "/metrics":
            for kind, value in services().gateway.stats.items():
                LLM_CALLS.labels(kind=kind).set(value)
        return await call_next(request)

    instrumentator.expose(app, include_in_schema=False)
    return app


app = create_app()
