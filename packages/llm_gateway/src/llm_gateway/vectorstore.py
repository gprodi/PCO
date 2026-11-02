"""Stockage vectoriel commun aux RAG du dépôt (cours de révision, copilote MicroForge).

Deux implémentations, même interface :

* :class:`MemoryVectorStore` — cosinus en Python pur, persistance JSON ; aucun serveur
  (développement, tests, petits volumes) ;
* :class:`PgVectorStore` — PostgreSQL + extension **pgvector** : colonne ``vector(n)``, index
  **HNSW** en distance cosinus, filtrage par groupe en SQL. Les vecteurs sont transmis sous forme
  de texte (``'[0.1, 0.2]'::vector``) : seul un pilote PostgreSQL (psycopg) est nécessaire.

:func:`open_vector_store` choisit selon l'URL : ``postgresql+psycopg://…`` → pgvector, sinon mémoire.
"""

from __future__ import annotations

import json
import math
import re
from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from llm_gateway.gateway import Gateway

_IDENT = re.compile(r"^[a-z_][a-z0-9_]{0,40}$")


@dataclass
class Record:
    """Un passage indexable : ``group`` sert au filtrage (cours, type de fiche…)."""

    id: str
    group: str
    title: str
    text: str
    meta: dict[str, Any] = field(default_factory=dict)


def _norm(v: Sequence[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [float(x) / n for x in v]


class VectorStore(ABC):
    """Interface minimale d'un index vectoriel."""

    @abstractmethod
    def upsert(self, records: Sequence[Record], vectors: Sequence[Sequence[float]]) -> None: ...

    @abstractmethod
    def delete_groups(self, groups: Iterable[str]) -> None: ...

    @abstractmethod
    def search(
        self, vector: Sequence[float], k: int = 5, groups: Sequence[str] | None = None
    ) -> list[tuple[float, Record]]:
        """Les ``k`` passages les plus proches (score = similarité cosinus, 1 = identique)."""

    @abstractmethod
    def count(self) -> int: ...

    def __len__(self) -> int:
        return self.count()


class MemoryVectorStore(VectorStore):
    """Index en mémoire ; ``save``/``load`` en JSON. Adapté à quelques milliers de passages."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._items: dict[str, tuple[Record, list[float]]] = {}
        if path is not None and path.exists():
            for row in json.loads(path.read_text(encoding="utf-8")):
                vec = row.pop("vector")
                self._items[row["id"]] = (Record(**row), vec)

    def upsert(self, records: Sequence[Record], vectors: Sequence[Sequence[float]]) -> None:
        for rec, vec in zip(records, vectors, strict=True):
            self._items[rec.id] = (rec, _norm(vec))

    def delete_groups(self, groups: Iterable[str]) -> None:
        drop = set(groups)
        self._items = {k: v for k, v in self._items.items() if v[0].group not in drop}

    def search(
        self, vector: Sequence[float], k: int = 5, groups: Sequence[str] | None = None
    ) -> list[tuple[float, Record]]:
        q = _norm(vector)
        allowed = set(groups) if groups else None
        scored = [
            (sum(a * b for a, b in zip(q, vec, strict=True)), rec)
            for rec, vec in self._items.values()
            if (allowed is None or rec.group in allowed) and len(vec) == len(q)
        ]
        scored.sort(key=lambda t: -t[0])
        return scored[:k]

    def count(self) -> int:
        return len(self._items)

    def save(self, path: Path | None = None) -> None:
        target = path or self.path
        if target is None:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        rows = [{**asdict(rec), "vector": vec} for rec, vec in self._items.values()]
        target.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


class PgVectorStore(VectorStore):
    """PostgreSQL + pgvector. La dimension de la colonne est fixée au premier ``upsert``."""

    def __init__(self, url: str, table: str = "rag_records") -> None:
        if not _IDENT.match(table):
            raise ValueError(f"Nom de table invalide : {table!r}")
        from sqlalchemy import create_engine, text  # extra « pgvector »

        self._text = text
        self.table = table
        self.engine = create_engine(url, pool_pre_ping=True)
        with self.engine.begin() as c:
            c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    @staticmethod
    def _literal(vec: Sequence[float]) -> str:
        return "[" + ",".join(f"{x:.7g}" for x in vec) + "]"

    def dimension(self) -> int | None:
        """Dimension de la colonne embedding, ou None si la table n'existe pas encore."""
        sql = self._text(
            "SELECT format_type(a.atttypid, a.atttypmod) FROM pg_attribute a "
            "WHERE a.attrelid = to_regclass(:t) AND a.attname = 'embedding'"
        )
        with self.engine.connect() as c:
            row = c.execute(sql, {"t": self.table}).scalar()
        return int(re.search(r"\((\d+)\)", row).group(1)) if row else None

    def _ensure(self, dim: int) -> None:
        current = self.dimension()
        if current is not None and current != dim:
            raise ValueError(
                f"La table {self.table} attend des vecteurs de dimension {current} (modèle "
                f"d'embedding différent ?) : reconstruire l'index avec reset=True."
            )
        t = self.table
        with self.engine.begin() as c:
            c.execute(
                self._text(
                    f"CREATE TABLE IF NOT EXISTS {t} (id TEXT PRIMARY KEY, grp TEXT NOT NULL, "
                    f"title TEXT NOT NULL, body TEXT NOT NULL, meta JSONB NOT NULL DEFAULT '{{}}', "
                    f"embedding vector({dim}) NOT NULL)"
                )
            )
            c.execute(self._text(f"CREATE INDEX IF NOT EXISTS {t}_grp ON {t} (grp)"))
            c.execute(
                self._text(
                    f"CREATE INDEX IF NOT EXISTS {t}_hnsw ON {t} "
                    "USING hnsw (embedding vector_cosine_ops)"
                )
            )

    def reset(self) -> None:
        with self.engine.begin() as c:
            c.execute(self._text(f"DROP TABLE IF EXISTS {self.table}"))

    def upsert(self, records: Sequence[Record], vectors: Sequence[Sequence[float]]) -> None:
        if not records:
            return
        self._ensure(len(vectors[0]))
        sql = self._text(
            f"INSERT INTO {self.table} (id, grp, title, body, meta, embedding) "
            "VALUES (:id, :grp, :title, :body, CAST(:meta AS JSONB), CAST(:emb AS vector)) "
            "ON CONFLICT (id) DO UPDATE SET grp = EXCLUDED.grp, title = EXCLUDED.title, "
            "body = EXCLUDED.body, meta = EXCLUDED.meta, embedding = EXCLUDED.embedding"
        )
        rows = [
            {
                "id": r.id,
                "grp": r.group,
                "title": r.title,
                "body": r.text,
                "meta": json.dumps(r.meta, ensure_ascii=False),
                "emb": self._literal(_norm(v)),
            }
            for r, v in zip(records, vectors, strict=True)
        ]
        with self.engine.begin() as c:
            c.execute(sql, rows)

    def delete_groups(self, groups: Iterable[str]) -> None:
        groups = list(groups)
        if not groups or self.dimension() is None:
            return
        with self.engine.begin() as c:
            c.execute(self._text(f"DELETE FROM {self.table} WHERE grp = ANY(:g)"), {"g": groups})

    def search(
        self, vector: Sequence[float], k: int = 5, groups: Sequence[str] | None = None
    ) -> list[tuple[float, Record]]:
        if self.dimension() is None:
            return []
        where = "WHERE grp = ANY(:g)" if groups else ""
        sql = self._text(
            f"SELECT id, grp, title, body, meta, 1 - (embedding <=> CAST(:v AS vector)) AS score "
            f"FROM {self.table} {where} ORDER BY embedding <=> CAST(:v AS vector) LIMIT :k"
        )
        params: dict[str, Any] = {"v": self._literal(_norm(vector)), "k": int(k)}
        if groups:
            params["g"] = list(groups)
        with self.engine.connect() as c:
            rows = c.execute(sql, params).mappings().all()
        return [
            (
                float(r["score"]),
                Record(r["id"], r["grp"], r["title"], r["body"], dict(r["meta"] or {})),
            )
            for r in rows
        ]

    def count(self) -> int:
        if self.dimension() is None:
            return 0
        with self.engine.connect() as c:
            return int(c.execute(self._text(f"SELECT count(*) FROM {self.table}")).scalar())


def open_vector_store(
    url: str | None, table: str = "rag_records", json_path: Path | None = None
) -> VectorStore:
    """pgvector si ``url`` désigne PostgreSQL, sinon index mémoire (persisté dans ``json_path``)."""
    if url and url.startswith("postgresql"):
        return PgVectorStore(url, table)
    return MemoryVectorStore(json_path)


def index_records(
    store: VectorStore,
    records: Sequence[Record],
    gateway: Gateway,
    batch: int = 32,
    replace_groups: bool = True,
) -> int:
    """Calcule les embeddings (titre + texte) et indexe ; remplace d'abord les groupes concernés."""
    if replace_groups:
        store.delete_groups({r.group for r in records})
    for start in range(0, len(records), batch):
        part = list(records[start : start + batch])
        vectors = gateway.embed([f"{r.title}\n{r.text}" for r in part])
        store.upsert(part, vectors)
    return len(records)
