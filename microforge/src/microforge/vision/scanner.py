"""Scanner d'inventaire : photo -> liste de composants du catalogue avec quantités.

Stratégie hybride (choix validé avec Gaël) :

* si un détecteur YOLO est disponible : il localise et classe ; les détections peu sûres ou hors
  catalogue sont découpées et confiées au VLM pour une identification fine (marquages) ;
* sinon : le VLM analyse la photo entière.

Chaque élément renvoyé indique sa ``source`` (yolo/vlm) et sa confiance : l'utilisateur valide ou
corrige, et ses corrections alimentent le monitoring du modèle (C11).
"""

from __future__ import annotations

import time
from collections import defaultdict

from llm_gateway import Gateway, LLMError, StructuredOutputError
from loguru import logger
from prometheus_client import Counter, Histogram
from pydantic import BaseModel, Field

from microforge.core.catalog import Catalog, get_catalog
from microforge.vision.detector import Detector
from microforge.vision.preprocess import clean_image, crop_jpeg

CONFIDENCE = Histogram(
    "mf_detection_confidence",
    "Confiance des détections",
    ["source"],
    buckets=[i / 10 for i in range(1, 11)],
)
DETECTIONS = Counter("mf_detections_total", "Composants détectés", ["source", "component"])
UNKNOWN = Counter(
    "mf_detections_unknown_total", "Objets non reconnus dans le catalogue", ["source"]
)
SCAN_LATENCY = Histogram("mf_scan_seconds", "Durée d'analyse d'une photo", ["mode"])

REFINE_BELOW = 0.55  # en dessous : on demande confirmation au VLM
MAX_REFINE = 6


class VisionItem(BaseModel):
    """Format demandé au VLM."""

    label: str = Field(description="nom du composant tel que reconnu (ex. 'capteur DHT22')")
    catalog_id: str | None = Field(
        default=None, description="identifiant du catalogue si reconnu, sinon null"
    )
    quantity: int = Field(default=1, ge=1, le=500)
    confidence: float = Field(default=0.5, ge=0, le=1)
    markings: str = Field(default="", description="inscriptions lues sur le composant")


class VisionInventory(BaseModel):
    items: list[VisionItem]


class ScanItem(BaseModel):
    component_id: str | None
    label: str
    quantity: int
    confidence: float
    source: str
    boxes: list[list[float]] = Field(default_factory=list)
    markings: str = ""


class ScanResult(BaseModel):
    items: list[ScanItem]
    unknown: list[ScanItem]
    width: int
    height: int
    sha256: str
    mode: str  # yolo+vlm | yolo | vlm
    model_version: str
    latency_ms: int


def _vlm_prompt(catalog: Catalog, single: bool) -> str:
    ids = ", ".join(sorted([*catalog.components, *catalog.boards]))
    what = (
        "Cette image montre UN composant électronique."
        if single
        else "Cette photo montre un stock de composants électroniques (bac, tiroir, table)."
    )
    return (
        f"{what} Identifie chaque type de composant et compte les exemplaires visibles. "
        "Lis les inscriptions (références) quand c'est possible. Pour catalog_id, utilise "
        f"UNIQUEMENT un de ces identifiants, ou null : {ids}. "
        "N'invente rien : en cas de doute, baisse la confiance."
    )


class InventoryScanner:
    """Analyse une photo de stock."""

    def __init__(
        self,
        gateway: Gateway | None,
        detector: Detector | None = None,
        catalog: Catalog | None = None,
    ) -> None:
        self.gateway = gateway
        self.detector = detector
        self.catalog = catalog or get_catalog()

    @property
    def model_version(self) -> str:
        return self.detector.version if self.detector else "vlm-only"

    def _resolve(self, ref: str | None) -> str | None:
        return self.catalog.resolve_fuzzy(ref) if ref else None

    def _vlm(self, jpeg: bytes, single: bool) -> list[VisionItem]:
        if self.gateway is None:
            return []
        try:
            inv = self.gateway.structured(
                _vlm_prompt(self.catalog, single),
                schema=VisionInventory,
                images=[jpeg],
                role="vision",
                max_tokens=2048,
            )
        except (LLMError, StructuredOutputError) as exc:
            logger.warning("VLM indisponible : {}", exc)
            return []
        return inv.items

    def scan(self, data: bytes, max_bytes: int = 8 * 1024 * 1024) -> ScanResult:
        start = time.perf_counter()
        clean = clean_image(data, max_bytes=max_bytes)
        grouped: dict[str, ScanItem] = {}
        unknown: list[ScanItem] = []

        def add(
            cid: str | None,
            label: str,
            conf: float,
            source: str,
            qty: int = 1,
            box=None,
            markings: str = "",
        ) -> None:
            CONFIDENCE.labels(source=source).observe(conf)
            if cid is None:
                UNKNOWN.labels(source=source).inc()
                unknown.append(
                    ScanItem(
                        component_id=None,
                        label=label,
                        quantity=qty,
                        confidence=conf,
                        source=source,
                        markings=markings,
                    )
                )
                return
            DETECTIONS.labels(source=source, component=cid).inc(qty)
            item = grouped.get(cid)
            if item is None:
                item = grouped[cid] = ScanItem(
                    component_id=cid, label=label, quantity=0, confidence=conf, source=source
                )
            item.quantity += qty
            item.confidence = min(item.confidence, conf)
            if box is not None:
                item.boxes.append([round(v, 1) for v in box])
            if markings:
                item.markings = markings

        if self.detector is not None:
            mode = "yolo"
            detections = self.detector.detect(clean.image)
            to_refine = [
                d for d in detections if d.component_id is None or d.confidence < REFINE_BELOW
            ]
            for d in detections:
                if d in to_refine[:MAX_REFINE] and self.gateway is not None:
                    continue
                add(d.component_id, d.label, d.confidence, "yolo", box=d.box)
            for d in to_refine[:MAX_REFINE]:
                if self.gateway is None:
                    break
                mode = "yolo+vlm"
                refined = self._vlm(crop_jpeg(clean.image, d.box), single=True)
                if refined:
                    r = refined[0]
                    cid = self._resolve(r.catalog_id) or self._resolve(r.label) or d.component_id
                    add(
                        cid,
                        r.label,
                        max(r.confidence, d.confidence),
                        "vlm",
                        box=d.box,
                        markings=r.markings,
                    )
                else:
                    add(d.component_id, d.label, d.confidence, "yolo", box=d.box)
        else:
            mode = "vlm"
            for r in self._vlm(clean.jpeg, single=False):
                cid = self._resolve(r.catalog_id) or self._resolve(r.label)
                add(cid, r.label, r.confidence, "vlm", qty=r.quantity, markings=r.markings)

        elapsed = time.perf_counter() - start
        SCAN_LATENCY.labels(mode=mode).observe(elapsed)
        items = sorted(grouped.values(), key=lambda i: (-i.quantity, i.component_id or ""))
        return ScanResult(
            items=items,
            unknown=unknown,
            width=clean.width,
            height=clean.height,
            sha256=clean.sha256,
            mode=mode,
            model_version=self.model_version,
            latency_ms=int(elapsed * 1000),
        )


def merge_counts(results: list[ScanResult]) -> dict[str, int]:
    """Additionne plusieurs photos (plusieurs tiroirs) en un inventaire {id: quantité}."""
    total: dict[str, int] = defaultdict(int)
    for r in results:
        for item in r.items:
            if item.component_id:
                total[item.component_id] += item.quantity
    return dict(total)
