"""Application qui journalise chaque requête (route, statut, durée, identifiant)."""

import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel, Field

from app.logs import setup_logging

setup_logging()
app = FastAPI(title="Application journalisée")


@app.middleware("http")
async def access_log(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    start = time.perf_counter()
    with logger.contextualize(request_id=request_id):
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001 - toute erreur est journalisée puis renvoyée en 500
            logger.exception("erreur non gérée", route=request.url.path)
            response = JSONResponse(
                {"detail": "Erreur interne", "request_id": request_id}, status_code=500
            )
        duree_ms = round((time.perf_counter() - start) * 1000, 1)
        level = "WARNING" if response.status_code >= 400 else "INFO"
        logger.log(
            level,
            "requête",
            methode=request.method,
            route=request.url.path,
            statut=response.status_code,
            duree_ms=duree_ms,
        )
    response.headers["X-Request-ID"] = request_id
    return response


class PredictIn(BaseModel):
    texte: str = Field(min_length=1, max_length=2000)


@app.post("/predict")
def predict(body: PredictIn) -> dict:
    label = "positif" if "super" in body.texte.lower() else "neutre"
    logger.info("prédiction", sentiment=label, longueur=len(body.texte))  # jamais le texte lui-même
    return {"sentiment": label}


@app.get("/boom")
def boom() -> dict:
    raise RuntimeError("panne simulée")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
