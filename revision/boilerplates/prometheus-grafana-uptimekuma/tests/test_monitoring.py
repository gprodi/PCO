import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).parents[1]
client = TestClient(app)


def test_metrics_follow_requests_and_predictions():
    assert client.post("/predict", json={"texte": "super produit"}).status_code == 200
    assert client.post("/predict", json={"texte": ""}).status_code == 422
    metrics = client.get("/metrics/").text
    assert 'http_requests_total{route="/predict",status="200"}' in metrics
    assert 'http_requests_total{route="/predict",status="422"}' in metrics
    assert "model_prediction_confidence_bucket" in metrics
    assert 'model_info{version="lexique-1"} 1.0' in metrics


def test_configuration_files_are_consistent():
    prom = yaml.safe_load((ROOT / "prometheus/prometheus.yml").read_text())
    assert prom["scrape_configs"][0]["static_configs"][0]["targets"] == ["api:8000"]
    rules = yaml.safe_load((ROOT / "prometheus/alerts.yml").read_text())["groups"][0]["rules"]
    assert {r["alert"] for r in rules} >= {"TauxErreursEleve", "LatenceP95Elevee", "DeriveConfianceModele"}
    dashboard = json.loads((ROOT / "grafana/dashboards/api-modele.json").read_text())
    exprs = " ".join(t["expr"] for p in dashboard["panels"] for t in p["targets"])
    for metric in ("http_requests_total", "http_request_duration_seconds_bucket", "model_prediction_confidence_bucket"):
        assert metric in exprs
