"""API d'un modèle, instrumentée pour Prometheus."""

import re
import time

from fastapi import FastAPI, Request
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app
from pydantic import BaseModel, Field

MODEL_VERSION = "lexique-1"

REQUESTS = Counter("http_requests_total", "Requêtes HTTP", ["route", "status"])
LATENCY = Histogram(
    "http_request_duration_seconds",
    "Durée des requêtes",
    ["route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5),
)
CONFIDENCE = Histogram(
    "model_prediction_confidence",
    "Confiance des prédictions",
    buckets=(0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0),
)
MODEL_INFO = Gauge("model_info", "Modèle en service", ["version"])
MODEL_INFO.labels(version=MODEL_VERSION).set(1)

app = FastAPI(title="API du modèle")
app.mount("/metrics", make_asgi_app())


@app.middleware("http")
async def measure(request: Request, call_next):
    if request.url.path.startswith("/metrics"):
        return await call_next(request)
    route = request.scope.get("route")
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        # gabarit de route (/items/{id}) plutôt que l'URL : nombre de séries borné
        path = getattr(request.scope.get("route", route), "path", request.url.path)
        LATENCY.labels(route=path).observe(time.perf_counter() - start)
        REQUESTS.labels(route=path, status=str(status)).inc()


class PredictIn(BaseModel):
    texte: str = Field(min_length=1, max_length=2000)


@app.post("/predict")
def predict(body: PredictIn) -> dict:
    mots = re.findall(r"\w+", body.texte.lower())
    pos = sum(m in {"bien", "bon", "super", "excellent"} for m in mots)
    neg = sum(m in {"mauvais", "nul", "lent", "cassé"} for m in mots)
    total = pos + neg
    label = "neutre" if pos == neg else ("positif" if pos > neg else "negatif")
    confidence = 0.5 if total == 0 else max(pos, neg) / total
    CONFIDENCE.observe(confidence)
    return {"sentiment": label, "confiance": round(confidence, 3), "modele": MODEL_VERSION}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "modele": MODEL_VERSION}
