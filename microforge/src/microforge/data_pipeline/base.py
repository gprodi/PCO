"""Socle commun des extracteurs : structure imposée par le critère C1.

Chaque extracteur suit le même squelette :

1. **point de lancement** : ``Extractor.run()`` (appelé par la CLI ou un flow Prefect) ;
2. **initialisation** : ``setup()`` (configuration, clients HTTP, connexions) ;
3. **règles de traitement** : ``extract()`` (requêtes, parsing, filtrage) ;
4. **gestion des erreurs** : exceptions typées, journalisées, statut « failed » dans le manifeste ;
5. **fin du traitement et sauvegarde** : ``save()`` -> ``data/raw/<source>/<date>/records.jsonl``
   + ``manifest.json`` (nombre de lignes, durée, statut, empreinte).
"""

from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

RAW_DIR = Path("data/raw")


class ExtractionError(RuntimeError):
    """Erreur de collecte (source injoignable, format inattendu, quota)."""


@dataclass
class RawPart:
    """Enregistrement brut d'un composant/offre, commun à toutes les sources (avant C3)."""

    source: str
    source_ref: str
    name: str | None = None
    mpn: str | None = None
    manufacturer: str | None = None
    description: str | None = None
    category: str | None = None
    package: str | None = None
    supply_text: str | None = None
    interfaces_text: str | None = None
    price: float | str | None = None
    currency: str | None = None
    stock: int | str | None = None
    url: str | None = None
    datasheet_url: str | None = None
    supplier: str | None = None
    collected_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Manifest:
    source: str
    kind: str  # rest | file | scraping | database | bigdata
    started_at: str
    finished_at: str | None = None
    status: str = "running"
    rows: int = 0
    duration_s: float = 0.0
    sha256: str | None = None
    message: str = ""
    params: dict[str, Any] = field(default_factory=dict)


class Extractor(ABC):
    """Classe de base d'un extracteur."""

    source: str = "base"
    kind: str = "rest"

    def __init__(self, out_dir: Path | None = None, **params: Any) -> None:
        self.out_dir = out_dir or RAW_DIR
        self.params = params

    def setup(self) -> None:  # noqa: B027 — 2. initialisation (optionnelle)
        """Prépare clients et connexions (surchargé si besoin)."""

    @abstractmethod
    def extract(self) -> list[dict[str, Any]]:  # 3. traitement
        """Collecte et renvoie des enregistrements (dict sérialisables)."""

    def teardown(self) -> None:  # noqa: B027 — optionnelle
        """Ferme les connexions."""

    def save(self, records: list[dict[str, Any]], manifest: Manifest) -> Path:  # 5. sauvegarde
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        target = self.out_dir / self.source / day
        target.mkdir(parents=True, exist_ok=True)
        payload = "\n".join(json.dumps(r, ensure_ascii=False, default=str) for r in records)
        (target / "records.jsonl").write_text(payload + ("\n" if payload else ""), encoding="utf-8")
        manifest.sha256 = hashlib.sha256(payload.encode()).hexdigest()
        (target / "manifest.json").write_text(
            json.dumps(asdict(manifest), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return target

    def run(self) -> tuple[list[dict[str, Any]], Manifest]:  # 1. point de lancement
        safe_params = {
            k: v
            for k, v in self.params.items()
            if isinstance(v, str | int | float | bool | list | type(None))
            and not any(s in k.lower() for s in ("key", "secret", "token", "password"))
        }
        manifest = Manifest(
            self.source, self.kind, datetime.now(UTC).isoformat(), params=safe_params
        )
        start = time.perf_counter()
        records: list[dict[str, Any]] = []
        try:
            self.setup()
            records = self.extract()
            manifest.status = "success"
        except Exception as exc:  # 4. gestion des erreurs : on journalise et on trace l'échec
            manifest.status = "failed"
            manifest.message = f"{type(exc).__name__}: {exc}"
            logger.exception("Extraction {} en échec", self.source)
        finally:
            self.teardown()
            manifest.rows = len(records)
            manifest.duration_s = round(time.perf_counter() - start, 3)
            manifest.finished_at = datetime.now(UTC).isoformat()
            path = self.save(records, manifest)
            logger.info(
                "{} : {} lignes ({}) -> {}", self.source, manifest.rows, manifest.status, path
            )
        return records, manifest


def to_dict(part: RawPart) -> dict[str, Any]:
    return asdict(part)
