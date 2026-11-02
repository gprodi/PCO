"""Tests d'intégration d'api_ia (C9 / C10) : vision, suggestions, génération, sécurité."""

from __future__ import annotations

import io
import zipfile

from llm_gateway import FakeProvider, Gateway
from microforge.common.security import create_access_token, signing_keys
from microforge.vision.detector import Detection, StaticDetector
from PIL import Image


def token_header(user_id: int = 1) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user_id, 'user', signing_keys())}"}


def test_health(ia_client):
    body = ia_client.get("/health").json()
    assert body["status"] == "ok" and body["llm_chain"] == ["fake"]


def test_requires_token(ia_client):
    assert ia_client.post("/v1/builds/suggest", json={"inventory": {}}).status_code == 401
    assert (
        ia_client.get("/v1/models/current", headers={"Authorization": "Bearer x"}).status_code
        == 401
    )


def test_current_model(ia_client):
    body = ia_client.get("/v1/models/current", headers=token_header()).json()
    assert body["detector"] == "vlm-only" and body["profile"] == "cpu"


def _services_with(fake: FakeProvider, detector=None):
    from microforge.api_ia.deps import services

    svc = services()
    gw = Gateway.fake(fake)
    svc.gateway = gw
    svc.scanner.gateway = gw
    svc.scanner.detector = detector
    svc.generator.gateway = gw
    return svc


def test_scan_vlm_only(ia_client, jpeg_with_gps):
    fake = FakeProvider(
        {
            "stock": {
                "items": [
                    {
                        "label": "capteur DHT22",
                        "catalog_id": "dht22",
                        "quantity": 2,
                        "confidence": 0.9,
                        "markings": "AM2302",
                    },
                    {
                        "label": "carte ESP32",
                        "catalog_id": None,
                        "quantity": 1,
                        "confidence": 0.8,
                        "markings": "",
                    },
                    {
                        "label": "objet mystère",
                        "catalog_id": None,
                        "quantity": 1,
                        "confidence": 0.3,
                        "markings": "",
                    },
                ]
            }
        }
    )
    _services_with(fake)
    r = ia_client.post(
        "/v1/vision/scan",
        files={"image": ("stock.jpg", jpeg_with_gps, "image/jpeg")},
        headers=token_header(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    ids = {i["component_id"]: i["quantity"] for i in body["items"]}
    assert ids == {"dht22": 2, "esp32-devkit-v1": 1}
    assert len(body["unknown"]) == 1
    assert body["mode"] == "vlm" and body["width"] <= 1280
    # La photo envoyée au VLM ne contient plus d'EXIF (GPS)
    sent = fake.calls[0].images[0].data
    assert not Image.open(io.BytesIO(sent)).getexif()


def test_scan_yolo_with_vlm_refinement(ia_client, jpeg_with_gps):
    detector = StaticDetector(
        [
            Detection("esp32_devkit", 0.93, (10, 10, 300, 200)),
            Detection("led", 0.88, (400, 400, 420, 440)),
            Detection("led", 0.81, (450, 400, 470, 440)),
            Detection("dht11", 0.41, (600, 100, 680, 220)),  # peu sûr -> VLM
        ],
        version="detector@test",
    )
    fake = FakeProvider(
        {
            "UN composant": {
                "items": [
                    {
                        "label": "DHT22",
                        "catalog_id": "dht22",
                        "quantity": 1,
                        "confidence": 0.85,
                        "markings": "AM2302",
                    }
                ]
            }
        }
    )
    _services_with(fake, detector)
    body = ia_client.post(
        "/v1/vision/scan",
        files={"image": ("s.jpg", jpeg_with_gps, "image/jpeg")},
        headers=token_header(),
    ).json()
    ids = {i["component_id"]: i for i in body["items"]}
    assert ids["led"]["quantity"] == 2 and ids["esp32-devkit-v1"]["source"] == "yolo"
    assert ids["dht22"]["source"] == "vlm" and ids["dht22"]["markings"] == "AM2302"
    assert body["mode"] == "yolo+vlm" and body["model_version"] == "detector@test"


def test_scan_rejects_bad_files(ia_client):
    h = token_header()
    assert (
        ia_client.post(
            "/v1/vision/scan", files={"image": ("x.jpg", b"pas une image", "image/jpeg")}, headers=h
        ).status_code
        == 422
    )
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="GIF")
    assert (
        ia_client.post(
            "/v1/vision/scan", files={"image": ("x.gif", buf.getvalue(), "image/gif")}, headers=h
        ).status_code
        == 422
    )


def test_suggest(ia_client):
    r = ia_client.post(
        "/v1/builds/suggest",
        json={"inventory": {"uno": 1, "led": 3, "pushbutton": 1}},
        headers=token_header(),
    )
    assert r.status_code == 200
    assert r.json()[0]["feasible_now"]


def test_generate_bundle_and_errors(ia_client):
    h = token_header()
    r = ia_client.post(
        "/v1/builds/generate",
        json={"template_id": "station-meteo-oled", "board": "esp32-devkit-v1"},
        headers=h,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] and "cablage.md" in body["files"] and body["libraries"]
    z = ia_client.post(
        "/v1/builds/bundle",
        json={"template_id": "veilleuse-auto", "board": "arduino-uno"},
        headers=h,
    )
    assert z.headers["content-type"] == "application/zip"
    assert any(
        n.endswith("wokwi/diagram.json") for n in zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    )
    assert ia_client.post("/v1/builds/generate", json={}, headers=h).status_code == 422
    bad = {
        "spec": {
            "title": "x",
            "board": "arduino-uno",
            "parts": [{"name": "a", "component": "inconnu"}],
        }
    }
    assert ia_client.post("/v1/builds/generate", json=bad, headers=h).status_code == 422


def test_from_goal_and_ideas(ia_client):
    idea = {
        "title": "Veilleuse",
        "description": "LED auto",
        "board": "arduino-uno",
        "uses_wifi": False,
        "parts": [
            {"name": "lumiere", "component": "ldr-module"},
            {"name": "led", "component": "led"},
        ],
        "logic": "if (lumiere_light_percent() < 30) { led_on(); } else { led_off(); }",
        "globals_extra": "",
        "setup_extra": "",
    }
    _services_with(FakeProvider({"veilleuse": idea, "stock": {"ideas": [idea]}}))
    h = token_header()
    r = ia_client.post(
        "/v1/builds/from-goal", json={"goal": "une veilleuse automatique"}, headers=h
    )
    assert r.status_code == 200 and r.json()["spec"]["title"] == "Veilleuse"
    ideas = ia_client.post(
        "/v1/builds/ideas",
        json={"inventory": {"arduino-uno": 1, "led": 2, "ldr-module": 1}},
        headers=h,
    ).json()
    assert ideas and ideas[0]["ok"]
    assert ia_client.post("/v1/builds/from-goal", json={"goal": "x"}, headers=h).status_code == 422


def test_metrics_expose_model_and_llm(ia_client):
    text = ia_client.get("/metrics").text
    assert "mf_detection_confidence" in text or "http_request" in text
