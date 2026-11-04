import sqlite3

import httpx

from etl import core

SAMPLE = [
    {"nom": "Lyon", "code": "69123", "population": 522250, "codesPostaux": ["69001", "69002"]},
    {"nom": "  Villeurbanne ", "code": "69266", "population": 162501, "codesPostaux": ["69100"]},
    {"nom": "Sans population", "code": "69999"},
    {"nom": "", "code": "69000", "population": 10},
]


def test_fetch_sends_department_and_fields():
    seen = {}

    def handler(request):
        seen.update(request.url.params)
        return httpx.Response(200, json=SAMPLE)

    rows = core.fetch("69", transport=httpx.MockTransport(handler))
    assert rows == SAMPLE and seen["codeDepartement"] == "69" and "population" in seen["fields"]


def test_clean_keeps_complete_rows():
    rows = core.clean(SAMPLE)
    assert [r["code"] for r in rows] == ["69123", "69266"]
    assert rows[1] == {"code": "69266", "nom": "Villeurbanne", "population": 162501, "code_postal": "69100"}


def test_save_is_idempotent(tmp_path):
    db = tmp_path / "c.db"
    rows = core.clean(SAMPLE)
    assert core.save(rows, db) == 2
    rows[0]["population"] = 600000
    core.save(rows, db)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*), MAX(population) FROM commune").fetchone() == (2, 600000)
