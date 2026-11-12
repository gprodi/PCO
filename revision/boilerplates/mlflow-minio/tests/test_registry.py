"""Registre local (SQLite + dossier) : mêmes appels que contre le serveur MLflow."""

import pytest
from fastapi.testclient import TestClient
from mlflow.tracking import MlflowClient


@pytest.fixture(autouse=True)
def local_mlflow(tmp_path, monkeypatch):
    import mlflow

    uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    monkeypatch.setenv("RELOAD_SECONDS", "0")
    mlflow.set_tracking_uri(uri)
    monkeypatch.chdir(tmp_path)  # artefacts dans le dossier temporaire


def test_champion_moves_only_when_f1_improves():
    import train

    first = train.train(C=1.0)
    assert first["version"] == "1" and first["promoted"] and first["f1"] > 0.9
    worse = train.train(C=0.001)  # régularisation excessive : F1 plus faible
    assert worse["version"] == "2" and not worse["promoted"]
    client = MlflowClient()
    assert str(client.get_model_version_by_alias(train.MODEL_NAME, "champion").version) == "1"
    assert str(client.get_model_version_by_alias(train.MODEL_NAME, "challenger").version) == "2"


def test_api_serves_champion_and_reloads_when_alias_moves():
    import serve
    import train

    train.train(C=1.0)
    train.train(C=0.5)  # au moins aussi bon : devient champion (version 2)
    with TestClient(serve.app) as client:
        assert client.get("/model").json()["version"] == "2"
        r = client.post("/predict", json={"mesures": [5.1, 3.5, 1.4, 0.2]})
        assert r.json()["espece"] == "setosa"
        MlflowClient().set_registered_model_alias(
            train.MODEL_NAME, "champion", "1"
        )  # retour arrière
        assert client.post("/reload").json() == {"recharge": True, "version": "1"}
        assert client.post("/predict", json={"mesures": [1, 2, 3]}).status_code == 422
