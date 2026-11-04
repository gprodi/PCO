"""Service minimal : santé et prédiction de démonstration."""

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Service")


class Mesure(BaseModel):
    temperature: float = Field(ge=-50, le=80)
    humidite: float = Field(ge=0, le=100)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/inconfort")
def inconfort(m: Mesure) -> dict:
    """Indice simple : 0 (confortable) à 1 (très inconfortable)."""
    chaleur = max(0.0, m.temperature - 24) / 10
    froid = max(0.0, 18 - m.temperature) / 10
    humidite = max(0.0, abs(m.humidite - 50) - 15) / 35
    return {"indice": round(min(1.0, chaleur + froid + humidite), 2)}
