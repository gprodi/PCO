"""Détecteur d'objets YOLO (Ultralytics) entraîné sur les composants électroniques (E3).

Chargement, par ordre de priorité :
1. ``MF_MLFLOW_MODEL_URI`` (ex. ``models:/microforge-detector@production``) : artefact ``best.pt``
   téléchargé depuis le registre MLflow (patron du cours MLOPS 2 : rechargement par alias) ;
2. ``MF_YOLO_WEIGHTS`` : chemin local vers ``best.pt`` ;
3. sinon : pas de détecteur -> le scanner bascule sur le VLM seul.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any, Protocol

import yaml
from loguru import logger
from PIL import Image


@dataclass
class Detection:
    label: str  # classe YOLO
    confidence: float
    box: tuple[float, float, float, float]  # x1, y1, x2, y2 (pixels)
    component_id: str | None = None


class Detector(Protocol):
    version: str

    def detect(self, image: Image.Image, conf: float = 0.25) -> list[Detection]: ...


@lru_cache(maxsize=1)
def class_mapping() -> dict[str, str]:
    """Classes du dataset -> identifiants du catalogue (ml/classes.yaml embarqué)."""
    text = resources.files("microforge.vision").joinpath("classes.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text)["classes"]


class YoloDetector:
    """Enveloppe d'un modèle Ultralytics."""

    def __init__(self, weights: str, version: str = "local") -> None:
        from ultralytics import YOLO  # import paresseux : dépendance lourde (extra « ml »)

        self.model = YOLO(weights)
        self.version = version

    def detect(self, image: Image.Image, conf: float = 0.25) -> list[Detection]:
        result = self.model.predict(image, conf=conf, verbose=False)[0]
        names: dict[int, str] = result.names
        mapping = class_mapping()
        out: list[Detection] = []
        for box, cls, score in zip(
            result.boxes.xyxy.tolist(),
            result.boxes.cls.tolist(),
            result.boxes.conf.tolist(),
            strict=True,
        ):
            label = names[int(cls)]
            out.append(
                Detection(
                    label=label,
                    confidence=float(score),
                    box=tuple(box),
                    component_id=mapping.get(label),
                )
            )
        return out


class StaticDetector:
    """Détecteur figé (tests, démonstration hors ligne)."""

    def __init__(self, detections: list[Detection], version: str = "static") -> None:
        self.detections = detections
        self.version = version

    def detect(self, image: Image.Image, conf: float = 0.25) -> list[Detection]:
        mapping = class_mapping()
        return [
            Detection(d.label, d.confidence, d.box, d.component_id or mapping.get(d.label))
            for d in self.detections
            if d.confidence >= conf
        ]


def load_detector(weights: str | None = None, mlflow_uri: str | None = None) -> Any | None:
    """Charge le détecteur configuré, ou None (repli VLM)."""
    try:
        if mlflow_uri:
            import mlflow

            path = mlflow.artifacts.download_artifacts(artifact_uri=f"{mlflow_uri}/weights/best.pt")
            return YoloDetector(path, version=mlflow_uri)
        if weights:
            return YoloDetector(weights, version=weights.rsplit("/", 1)[-1])
    except Exception as exc:  # modèle absent, MLflow injoignable, ultralytics non installé…
        logger.warning("Détecteur YOLO indisponible ({}), repli sur le VLM", exc)
    return None
