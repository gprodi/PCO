"""API d'IA : expose le modèle."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from loguru import logger
from pydantic import BaseModel, Field

from api_ia import model
from common.logs import setup_logging
from common.security import require_api_key


class PredictIn(BaseModel):
    texte: str = Field(min_length=1, max_length=2000)


class PredictOut(BaseModel):
    sentiment: str
    score: float
    modele: str


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging("api_ia")
    yield


app = FastAPI(title="API IA", lifespan=lifespan)


@app.post("/predict", dependencies=[Depends(require_api_key)])
def predict(body: PredictIn) -> PredictOut:
    label, score = model.predict(body.texte)
    logger.info("prédiction", sentiment=label, score=score, longueur=len(body.texte))
    return PredictOut(sentiment=label, score=score, modele=model.VERSION)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "modele": model.VERSION}
