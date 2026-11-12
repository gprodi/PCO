import io
import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from app import main
from app.logs import setup_logging

ROOT = Path(__file__).parents[1]


def records(buffer: io.StringIO) -> list[dict]:
    return [json.loads(line)["record"] for line in buffer.getvalue().splitlines() if line.strip()]


def test_each_request_is_logged_as_json_with_its_id():
    buffer = io.StringIO()
    setup_logging(buffer)
    client = TestClient(main.app, raise_server_exceptions=False)
    r = client.post("/predict", json={"texte": "super produit"}, headers={"X-Request-ID": "abc123"})
    assert r.headers["x-request-id"] == "abc123"
    logs = records(buffer)
    prediction = next(x for x in logs if x["message"] == "prédiction")
    access = next(x for x in logs if x["message"] == "requête")
    assert prediction["extra"] == {"request_id": "abc123", "sentiment": "positif", "longueur": 13}
    assert access["extra"]["statut"] == 200 and access["extra"]["route"] == "/predict"
    assert (
        "super produit" not in buffer.getvalue()
    )  # le texte de l'utilisateur n'est pas journalisé


def test_errors_are_logged_with_level_error():
    buffer = io.StringIO()
    setup_logging(buffer)
    client = TestClient(main.app, raise_server_exceptions=False)
    r = client.get("/boom")
    assert r.status_code == 500 and r.json()["request_id"]
    levels = {x["message"]: x["level"]["name"] for x in records(buffer)}
    assert levels["erreur non gérée"] == "ERROR" and levels["requête"] == "WARNING"


def test_collection_configuration():
    loki = yaml.safe_load((ROOT / "loki/config.yaml").read_text())
    assert loki["limits_config"]["retention_period"] == "720h"
    alloy = (ROOT / "alloy/config.alloy").read_text()
    for block in (
        'discovery.docker "conteneurs"',
        'loki.source.docker "conteneurs"',
        'loki.write "local"',
    ):
        assert block in alloy
    assert alloy.count("{") == alloy.count("}")
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    assert set(compose["services"]) == {"app", "loki", "alloy", "grafana"}
