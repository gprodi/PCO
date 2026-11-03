import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("temperature", "humidite", "indice"),
    [(21, 50, 0.0), (34, 50, 1.0), (13, 50, 0.5), (21, 100, 1.0)],
)
def test_inconfort(temperature, humidite, indice):
    r = client.post("/inconfort", json={"temperature": temperature, "humidite": humidite})
    assert r.status_code == 200 and r.json()["indice"] == indice


def test_validation():
    assert client.post("/inconfort", json={"temperature": 200, "humidite": 50}).status_code == 422
