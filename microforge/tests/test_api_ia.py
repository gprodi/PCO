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


def test_generate_returns_atelier_and_template(ia_client):
    """La page Projet (PWA) a tout ce qu'il faut : atelier virtuel, notions, références, cartes."""
    r = ia_client.post(
        "/v1/builds/generate",
        json={"template_id": "station-meteo-oled", "board": "esp32-devkit-v1"},
        headers=token_header(),
    )
    body = r.json()
    atelier = body["atelier"]
    assert atelier["template"] == "station-meteo-oled" and atelier["code"]
    assert atelier["wiring"]["pins"] and atelier["wiring"]["board"]["labels"]
    assert {p["name"] for p in atelier["parts"]} == {p["name"] for p in body["spec"]["parts"]}
    tpl = body["template"]
    assert tpl["id"] == "station-meteo-oled" and tpl["learning"] and tpl["references"]
    assert all(set(ref) >= {"site", "title", "url"} for ref in tpl["references"])
    assert tpl["theme"] and tpl["theme"]["titre"]
    from microforge.core.catalog import get_catalog

    catalog = get_catalog()
    ids = [b["id"] for b in tpl["boards"]]
    assert "esp32-devkit-v1" in ids
    assert all(catalog.template_fits("station-meteo-oled", catalog.boards[b]) for b in ids)


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
    assert r.json()["template"] is None  # projet libre : pas de modèle du catalogue
    assert r.json()["origin"] == "ia" and "ni compilé" in r.json()["notice"]
    assert r.json()["atelier"]["code"]  # mais la logique simple se simule
    ideas = ia_client.post(
        "/v1/builds/ideas",
        json={"inventory": {"arduino-uno": 1, "led": 2, "ldr-module": 1}},
        headers=h,
    ).json()
    assert ideas and ideas[0]["ok"]
    assert ia_client.post("/v1/builds/from-goal", json={"goal": "x"}, headers=h).status_code == 422


def test_from_goal_sans_ia_le_dit(ia_client):
    """IA injoignable : le modèle le plus proche est renvoyé, et la réponse le dit."""
    _services_with(FakeProvider(fail=True))
    r = ia_client.post(
        "/v1/builds/from-goal",
        json={
            "goal": "Alarme de cave : un buzzer sonne si l'eau monte",
            "components": ["water-level-sensor", "buzzer"],
        },
        headers=token_header(),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["origin"] == "repli" and body["spec"]["template_id"]
    assert body["notice"].startswith("Aucune IA n'a répondu")
    assert "modèle du catalogue le plus proche" in body["notice"]
    assert body["spec"]["title"] in body["notice"]
    assert body["template"] is not None  # modèle du catalogue : choix de carte, zip


def test_generation_par_modele_sans_provenance(ia_client):
    r = ia_client.post(
        "/v1/builds/generate",
        json={"template_id": "veilleuse-auto", "board": "arduino-uno"},
        headers=token_header(),
    )
    assert r.status_code == 200 and r.json()["origin"] is None and r.json()["notice"] is None


def test_metrics_expose_model_and_llm(ia_client):
    text = ia_client.get("/metrics").text
    assert "mf_detection_confidence" in text or "http_request" in text


def test_explore_ideas_endpoint(ia_client):
    r = ia_client.post(
        "/v1/ideas/explore",
        json={"inventory": {"uno": 1, "led": 3, "pushbutton": 2, "buzzer": 1}},
        headers=token_header(),
    )
    assert r.status_code == 200
    jeux = next(t for t in r.json() if t["id"] == "jeux")
    assert jeux["idees"][0]["realisable"] is True
    assert ia_client.post("/v1/ideas/explore", json={}).status_code == 401


def test_inspiration_endpoint(ia_client):
    r = ia_client.get("/v1/ideas/inspiration", headers=token_header())
    assert r.status_code == 200
    body = r.json()
    assert body["chiffres"]["modeles_generables"] >= 45
    assert body["chiffres"]["idees"] >= 120
    assert [s["etape"] for s in body["parcours"]] == sorted(s["etape"] for s in body["parcours"])
    assert body["parcours"][-1]["projets"][0]["id"].startswith("robot")
    assert all(v["url"].startswith("https://") for v in body["vitrine"])
    assert ia_client.get("/v1/ideas/inspiration").status_code == 401


def test_streamlit_client_routes_exist_in_apis(data_client, ia_client):
    """Contrat : chaque route appelée par le client Streamlit existe dans api_data ou api_ia."""
    import re
    from pathlib import Path

    from microforge.app_streamlit import client as client_mod

    source = Path(client_mod.__file__).read_text(encoding="utf-8")
    used = set(re.findall(r'"(/v1/[a-z0-9/_\-{}]+)"', source))
    routes = {
        re.sub(r"\{[^}]+\}", "{}", p)
        for c in (data_client, ia_client)
        for p in c.get("/openapi.json").json()["paths"]
    }
    missing = {u for u in used if re.sub(r"\{[^}]+\}", "{}", u) not in routes}
    assert not missing, f"routes inconnues des API : {missing}"
    assert "/v1/ideas/explore" in used and "/v1/ideas/inspiration" in used


def test_cle_publique_relue_apres_redemarrage_d_api_data(ia_client, monkeypatch, mf_env):
    """Clés éphémères (dev) : api_data redémarrée signe avec une nouvelle clé ; api_ia la relit."""
    import httpx
    from microforge.api_ia import deps
    from microforge.common.security import create_access_token, generate_keypair
    from microforge.common.settings import get_settings

    monkeypatch.delenv("MF_JWT_PUBLIC_KEY")
    get_settings.cache_clear()
    old, new = mf_env, generate_keypair()
    served = {"pem": old.public_pem}
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return httpx.Response(200, text=served["pem"], request=httpx.Request("GET", url))

    monkeypatch.setattr(deps.httpx, "get", fake_get)
    monkeypatch.setattr(deps, "_last_key_refresh", -1e9)
    deps.public_key.cache_clear()
    old_token = {"Authorization": f"Bearer {create_access_token(1, 'user', old)}"}
    assert ia_client.get("/v1/models/current", headers=old_token).status_code == 200
    served["pem"] = new.public_pem  # api_data redémarrée : nouvelles clés
    new_token = {"Authorization": f"Bearer {create_access_token(1, 'user', new)}"}
    assert ia_client.get("/v1/models/current", headers=new_token).status_code == 200
    assert len(calls) == 2  # clé lue au premier jeton, relue une fois après le changement
    # Un jeton signé par une clé inconnue reste refusé, sans relecture en boucle.
    rogue = {"Authorization": f"Bearer {create_access_token(1, 'user', generate_keypair())}"}
    assert ia_client.get("/v1/models/current", headers=rogue).status_code == 401
    assert ia_client.get("/v1/models/current", headers=rogue).status_code == 401
    assert len(calls) == 2
