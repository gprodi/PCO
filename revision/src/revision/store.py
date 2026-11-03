"""Index sémantique des cours, sur le stockage vectoriel commun (``llm_gateway.vectorstore``).

* par défaut : index **mémoire** persisté en JSON (``content/_index.json``) — aucun serveur ;
* avec ``REVISION_VECTOR_URL=postgresql+psycopg://…`` : **PostgreSQL + pgvector** (table
  ``revision_chunks``, index HNSW cosinus, filtrage par cours en SQL) — même interface.

Volume visé : quelques milliers de passages ; pgvector sert dès que l'index est partagé (API dans un
conteneur, plusieurs postes) ou grossit (ajout de cours, documents complémentaires).
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

from llm_gateway import Gateway
from llm_gateway.vectorstore import (
    MemoryVectorStore,
    PgVectorStore,
    Record,
    VectorStore,
    index_records,
)

from revision.ingest.chunker import Chunk

ENV_URL = "REVISION_VECTOR_URL"
PG_TABLE = "revision_chunks"


def _hit(rec: Record) -> dict:
    """Passage au format attendu par le RAG (``id``, ``course``, ``heading``, ``text``)."""
    return {"id": rec.id, "course": rec.group, "heading": rec.title, "text": rec.text}


class VectorIndex:
    """Passages de cours indexés ; ``course`` = groupe du stockage vectoriel."""

    def __init__(self, items: list[dict] | None = None, store: VectorStore | None = None) -> None:
        self.store = store if store is not None else MemoryVectorStore()  # vide = falsy (__len__)
        if items:  # format historique : {"id","course","heading","text","vector"}
            self.store.upsert(
                [Record(i["id"], i["course"], i["heading"], i["text"]) for i in items],
                [i["vector"] for i in items],
            )

    @property
    def backend(self) -> str:
        return "pgvector" if isinstance(self.store, PgVectorStore) else "mémoire"

    def add(self, chunks: Sequence[Chunk], gateway: Gateway, batch: int = 32) -> None:
        """Indexe des passages ; ceux des cours concernés sont d'abord remplacés."""
        records = [Record(c.id, c.course, c.heading, c.text) for c in chunks]
        index_records(self.store, records, gateway, batch=batch)

    def search(
        self, query_vector: Sequence[float], k: int = 5, courses: list[str] | None = None
    ) -> list[tuple[float, dict]]:
        return [(s, _hit(r)) for s, r in self.store.search(query_vector, k=k, groups=courses)]

    def clear(self) -> None:
        if isinstance(self.store, PgVectorStore):
            self.store.reset()
        else:
            empty = MemoryVectorStore()
            empty.path = getattr(self.store, "path", None)
            self.store = empty

    def save(self, path: Path | None = None) -> None:
        """Persistance JSON de l'index mémoire ; sans objet avec pgvector (déjà en base)."""
        if isinstance(self.store, MemoryVectorStore):
            self.store.save(path)

    def __len__(self) -> int:
        return len(self.store)

    @classmethod
    def load(cls, path: Path) -> VectorIndex:
        """Index mémoire depuis un JSON (accepte aussi l'ancien format de ``_index.json``)."""
        if path.exists():
            rows = json.loads(path.read_text(encoding="utf-8"))
            if rows and "course" in rows[0]:
                idx = cls(rows, MemoryVectorStore())
                idx.store.path = path
                return idx
        return cls(store=MemoryVectorStore(path))


@lru_cache(maxsize=4)
def _pg_store(url: str) -> PgVectorStore:
    """Un moteur SQLAlchemy (pool de connexions) par URL, partagé entre les requêtes."""
    return PgVectorStore(url, PG_TABLE)


def open_course_index(content_dir: Path, url: str | None = None) -> VectorIndex:
    """pgvector si ``url`` (ou ``REVISION_VECTOR_URL``) désigne PostgreSQL, sinon JSON local."""
    url = url if url is not None else os.environ.get(ENV_URL, "")
    if url.startswith("postgresql"):
        return VectorIndex(store=_pg_store(url))
    return VectorIndex.load(content_dir / "_index.json")
