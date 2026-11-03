"""Stockage vectoriel : index mémoire (toujours testé) et PostgreSQL + pgvector (si disponible).

Le test PostgreSQL est marqué ``pgvector`` : il tourne quand ``PGVECTOR_TEST_URL`` pointe vers une
base avec l'extension (en CI : service ``pgvector/pgvector:pg17``), sinon il est ignoré.
"""

from __future__ import annotations

import os
import uuid

import pytest
from llm_gateway import FakeProvider, Gateway
from llm_gateway.vectorstore import (
    MemoryVectorStore,
    PgVectorStore,
    Record,
    VectorStore,
    index_records,
    open_vector_store,
)

DOCS = [
    Record("mlflow#0", "mlflow", "MLflow", "suivi des expériences runs paramètres métriques"),
    Record("mlflow#1", "mlflow", "Registre", "registre de modèles alias champion production"),
    Record("fastapi#0", "fastapi", "FastAPI", "routes asynchrones validation pydantic openapi"),
    Record("docker#0", "docker", "Docker", "image conteneur dockerfile couches cache", {"n": 1}),
]


def gateway() -> Gateway:
    return Gateway.fake(FakeProvider(embed_dim=128))


def exercise(store: VectorStore) -> None:
    """Scénario commun aux deux implémentations."""
    gw = gateway()
    assert index_records(store, DOCS, gw, batch=3) == 4
    assert len(store) == 4

    (qv,) = gw.embed(["registre de modèles alias champion"])
    score, best = store.search(qv, k=2)[0]
    assert best.id == "mlflow#1" and 0.5 < score <= 1.0001

    hits = store.search(qv, k=5, groups=["docker", "fastapi"])
    assert {r.group for _, r in hits} <= {"docker", "fastapi"}
    assert next(r for _, r in hits if r.id == "docker#0").meta == {"n": 1}

    # Réindexer un groupe remplace ses passages (pas de doublon, anciens retirés)
    index_records(store, [Record("mlflow#9", "mlflow", "MLflow", "nouveau texte")], gw)
    assert len(store) == 3
    assert all(r.group != "mlflow" or r.id == "mlflow#9" for _, r in store.search(qv, k=10))

    assert store.get("fastapi#0").title == "FastAPI" and store.get("docker#0").meta == {"n": 1}
    assert store.get("absent") is None

    store.delete_groups(["docker"])
    assert len(store) == 2
    store.delete_groups([])  # sans effet
    assert len(store) == 2


def test_memory_store_scenario_and_persistence(tmp_path):
    path = tmp_path / "index.json"
    store = MemoryVectorStore(path)
    exercise(store)
    store.save()
    reloaded = MemoryVectorStore(path)
    assert len(reloaded) == 2
    (qv,) = gateway().embed(["routes asynchrones pydantic"])
    assert reloaded.search(qv, k=1)[0][1].id == "fastapi#0"


def test_memory_store_ignores_other_dimensions_and_saves_nowhere_without_path():
    store = MemoryVectorStore()
    store.upsert([DOCS[0]], [[1.0, 0.0, 0.0]])
    assert store.search([1.0, 0.0], k=3) == []  # autre modèle d'embedding : ignoré
    assert store.search([2.0, 0.0, 0.0])[0][0] == pytest.approx(1.0)  # normalisé
    store.save()  # pas de chemin : rien à écrire, pas d'erreur
    with pytest.raises(ValueError):
        store.upsert(DOCS[:2], [[1.0, 0.0, 0.0]])  # un vecteur par passage


def test_open_vector_store_picks_memory_without_postgres_url(tmp_path):
    assert isinstance(open_vector_store(None), MemoryVectorStore)
    store = open_vector_store("sqlite:///x.db", json_path=tmp_path / "i.json")
    assert isinstance(store, MemoryVectorStore) and store.path == tmp_path / "i.json"


def test_pg_store_rejects_unsafe_table_name():
    with pytest.raises(ValueError, match="table"):
        PgVectorStore("postgresql+psycopg://x@localhost/db", table="rag; DROP TABLE x")


PG_URL = os.environ.get("PGVECTOR_TEST_URL")


@pytest.mark.pgvector
@pytest.mark.skipif(not PG_URL, reason="PGVECTOR_TEST_URL non défini (base PostgreSQL + pgvector)")
def test_pgvector_store_scenario():
    table = f"t_{uuid.uuid4().hex[:12]}"
    store = open_vector_store(PG_URL, table=table)
    assert isinstance(store, PgVectorStore)
    try:
        assert store.dimension() is None and len(store) == 0 and store.get("x") is None
        assert store.search([1.0] * 128) == []
        store.delete_groups(["rien"])  # table absente : sans effet
        exercise(store)
        assert store.dimension() == 128
        with store.engine.connect() as c:
            indexes = c.exec_driver_sql(
                "SELECT indexdef FROM pg_indexes WHERE tablename = %s", (table,)
            ).scalars()
            assert any("hnsw" in d and "vector_cosine_ops" in d for d in indexes)
        with pytest.raises(ValueError, match="dimension"):
            store.upsert([DOCS[0]], [[1.0, 0.0]])  # autre modèle d'embedding
        store.reset()
        assert store.dimension() is None
    finally:
        store.reset()
        store.engine.dispose()
