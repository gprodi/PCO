"""Index sémantique léger (JSON + cosinus en Python pur) — Chroma en option (extra « chroma »).

Volume visé : quelques milliers de passages -> pas besoin d'un serveur vectoriel (sobriété).
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from pathlib import Path

from llm_gateway import Gateway

from revision.ingest.chunker import Chunk


class VectorIndex:
    def __init__(self, items: list[dict] | None = None) -> None:
        self.items = items or []  # {"id","course","heading","text","vector"}

    @staticmethod
    def _norm(v: list[float]) -> list[float]:
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def add(self, chunks: list[Chunk], gateway: Gateway, batch: int = 32) -> None:
        self.items = [i for i in self.items if i["course"] not in {c.course for c in chunks}]
        for start in range(0, len(chunks), batch):
            part = chunks[start : start + batch]
            vectors = gateway.embed([f"{c.heading}\n{c.text}" for c in part])
            for c, v in zip(part, vectors, strict=True):
                self.items.append({**asdict(c), "vector": self._norm(v)})

    def search(
        self, query_vector: list[float], k: int = 5, courses: list[str] | None = None
    ) -> list[tuple[float, dict]]:
        q = self._norm(query_vector)
        scored = []
        for item in self.items:
            if courses and item["course"] not in courses:
                continue
            if len(item["vector"]) != len(q):
                continue
            scored.append((sum(a * b for a, b in zip(q, item["vector"], strict=True)), item))
        scored.sort(key=lambda t: -t[0])
        return scored[:k]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.items, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> VectorIndex:
        return cls(json.loads(path.read_text(encoding="utf-8")) if path.exists() else [])
