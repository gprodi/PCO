"""Tests d'intégration d'api_data (C5 / C9 / C17) : tous les points de terminaison."""

from __future__ import annotations

import jwt
from conftest import register_and_login


def auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_health_and_metrics(data_client):
    assert data_client.get("/health").json()["status"] == "ok"
    metrics = data_client.get("/metrics")
    assert (
        metrics.status_code == 200 and "http_requests_total" in metrics.text
    ) or "http_request" in metrics.text


def test_security_headers(data_client):
    r = data_client.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "X-Request-ID" in r.headers


def test_register_validation_and_conflict(data_client):
    bad = data_client.post(
        "/v1/auth/register", json={"username": "a", "email": "pas-un-mail", "password": "court"}
    )
    assert bad.status_code == 422
    register_and_login(data_client, "gael")
    dup = data_client.post(
        "/v1/auth/register",
        json={"username": "gael", "email": "x@example.org", "password": "motdepasse123"},
    )
    assert dup.status_code == 409


def test_login_by_email_and_wrong_password(data_client):
    register_and_login(data_client, "gael", email="Gael@Example.org")
    ok = data_client.post(
        "/v1/auth/token", data={"username": "gael@example.org", "password": "motdepasse123"}
    )
    assert ok.status_code == 200
    ko = data_client.post("/v1/auth/token", data={"username": "gael", "password": "mauvais123"})
    assert ko.status_code == 401
    unknown = data_client.post(
        "/v1/auth/token", data={"username": "personne", "password": "motdepasse123"}
    )
    assert unknown.status_code == 401


def test_protected_routes_require_token(data_client):
    for path in ("/v1/users/me", "/v1/inventory", "/v1/components", "/v1/projects"):
        assert data_client.get(path).status_code == 401
    assert (
        data_client.get(
            "/v1/users/me", headers={"Authorization": "Bearer faux.jeton.x"}
        ).status_code
        == 401
    )


def test_rejects_alg_none_and_refresh_as_access(data_client, mf_env):
    tokens = register_and_login(data_client)
    forged = jwt.encode({"sub": "1", "type": "access"}, key="", algorithm="none")
    assert (
        data_client.get("/v1/users/me", headers={"Authorization": f"Bearer {forged}"}).status_code
        == 401
    )
    refresh_as_access = {"Authorization": f"Bearer {tokens['refresh_token']}"}
    assert data_client.get("/v1/users/me", headers=refresh_as_access).status_code == 401


def test_refresh_rotation_and_reuse_detection(data_client):
    tokens = register_and_login(data_client)
    r1 = data_client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r1.status_code == 200
    new = r1.json()
    # Réutilisation de l'ancien refresh -> 401 et révocation de la famille
    reuse = data_client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse.status_code == 401
    assert (
        data_client.post(
            "/v1/auth/refresh", json={"refresh_token": new["refresh_token"]}
        ).status_code
        == 401
    )


def test_logout_revokes_family(data_client):
    tokens = register_and_login(data_client)
    assert (
        data_client.post(
            "/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 204
    )
    assert (
        data_client.post(
            "/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )


def test_public_key_endpoint(data_client, mf_env):
    assert "BEGIN PUBLIC KEY" in data_client.get("/v1/auth/public-key").text


def test_me_never_exposes_sensitive_fields(data_client):
    tokens = register_and_login(data_client)
    me = data_client.get("/v1/users/me", headers=auth(tokens)).json()
    assert me["username"] == "gael"
    assert not {"password_hash", "email_encrypted", "email_index", "email"} & set(me)


def test_catalog_endpoints(data_client):
    h = auth(register_and_login(data_client))
    comps = data_client.get("/v1/components", params={"q": "dht"}, headers=h).json()
    assert any(c["id"] == "dht22" for c in comps)
    assert data_client.get("/v1/components", params={"limit": 500}, headers=h).status_code == 422
    detail = data_client.get("/v1/components/dht22", headers=h).json()
    assert detail["pins"] and "DHT sensor library" in detail["libraries"]
    assert data_client.get("/v1/components/esp32-devkit-v1", headers=h).json()["pins"]
    assert data_client.get("/v1/components/inconnu", headers=h).status_code == 404
    assert len(data_client.get("/v1/boards", headers=h).json()) >= 6
    assert len(data_client.get("/v1/templates", headers=h).json()) >= 30
    assert data_client.get("/v1/components/dht22/offers", headers=h).json() == []


def test_inventory_crud_bola_and_summary(data_client):
    a = auth(register_and_login(data_client, "alice"))
    b = auth(register_and_login(data_client, "bob"))
    item = data_client.post(
        "/v1/inventory",
        json={"component_id": "dht22", "quantity": 2, "location": "tiroir 1"},
        headers=a,
    ).json()
    again = data_client.post(
        "/v1/inventory",
        json={"component_id": "dht22", "quantity": 1, "location": "tiroir 1"},
        headers=a,
    ).json()
    assert again["id"] == item["id"] and again["quantity"] == 3
    assert (
        data_client.post("/v1/inventory", json={"component_id": "inconnu"}, headers=a).status_code
        == 422
    )
    # Bob ne voit ni ne modifie l'article d'Alice (BOLA)
    assert (
        data_client.patch(
            f"/v1/inventory/{item['id']}", json={"quantity": 0}, headers=b
        ).status_code
        == 404
    )
    assert data_client.delete(f"/v1/inventory/{item['id']}", headers=b).status_code == 404
    assert data_client.get("/v1/inventory", headers=b).json() == []
    patched = data_client.patch(
        f"/v1/inventory/{item['id']}", json={"quantity": 5}, headers=a
    ).json()
    assert patched["quantity"] == 5
    bulk = data_client.post(
        "/v1/inventory/bulk",
        json={
            "items": [{"component_id": "led", "quantity": 4}, {"component_id": "esp32-devkit-v1"}],
            "location": "bac",
        },
        headers=a,
    )
    assert bulk.status_code == 200 and len(bulk.json()) == 2
    summary = data_client.get("/v1/inventory/summary", headers=a).json()
    assert summary == {"dht22": 5, "led": 4, "esp32-devkit-v1": 1}
    assert data_client.delete(f"/v1/inventory/{item['id']}", headers=a).status_code == 204


def test_photos_and_feedback(data_client):
    a = auth(register_and_login(data_client, "alice"))
    b = auth(register_and_login(data_client, "bob"))
    photo = data_client.post(
        "/v1/photos", json={"sha256": "a" * 64, "width": 800, "height": 600}, headers=a
    ).json()
    fb = data_client.post(
        "/v1/feedback",
        json={
            "kind": "wrong_label",
            "predicted_component_id": "dht11",
            "corrected_component_id": "dht22",
            "photo_id": photo["id"],
            "confidence": 0.4,
        },
        headers=a,
    )
    assert fb.status_code == 201
    assert (
        data_client.post(
            "/v1/feedback", json={"kind": "correct", "photo_id": photo["id"]}, headers=b
        ).status_code
        == 404
    )
    assert (
        data_client.post("/v1/feedback", json={"kind": "nimportequoi"}, headers=a).status_code
        == 422
    )
    assert "mf_detection_correction_rate" in data_client.get("/metrics").text


def test_projects_and_shopping_list(data_client):
    h = auth(register_and_login(data_client))
    from microforge.core import ProjectBuilder

    spec = ProjectBuilder().spec_from_template("radar-de-recul", "esp32-devkit-v1")
    p = data_client.post(
        "/v1/projects",
        json={
            "title": spec.title,
            "board_id": spec.board,
            "template_id": "radar-de-recul",
            "spec": spec.model_dump(),
        },
        headers=h,
    )
    assert p.status_code == 201
    pid = p.json()["id"]
    assert (
        data_client.get(f"/v1/projects/{pid}", headers=h).json()["spec"]["board"]
        == "esp32-devkit-v1"
    )
    assert len(data_client.get("/v1/projects", headers=h).json()) == 1
    data_client.post("/v1/inventory", json={"component_id": "esp32-devkit-v1"}, headers=h)
    sl = data_client.post("/v1/shopping-list", json={"project_id": pid}, headers=h).json()
    assert "esp32-devkit-v1" not in [line["component"] for line in sl["to_buy"]]
    assert sl["total_eur"] > 0
    tpl = data_client.post(
        "/v1/shopping-list",
        json={"template_id": "veilleuse-auto", "board_id": "arduino-uno"},
        headers=h,
    )
    assert tpl.status_code == 200
    assert data_client.post("/v1/shopping-list", json={}, headers=h).status_code == 422
    other = auth(register_and_login(data_client, "intrus"))
    assert data_client.get(f"/v1/projects/{pid}", headers=other).status_code == 404
    assert data_client.delete(f"/v1/projects/{pid}", headers=h).status_code == 204


def test_admin_requires_role(data_client):
    from microforge.api_data.db import User, get_engine
    from sqlmodel import Session, select

    h = auth(register_and_login(data_client, "admin"))
    assert data_client.get("/v1/admin/ingestion-runs", headers=h).status_code == 403
    with Session(get_engine()) as s:
        u = s.exec(select(User).where(User.username == "admin")).one()
        u.role = "admin"
        s.add(u)
        s.commit()
    h = auth(
        data_client.post(
            "/v1/auth/token", data={"username": "admin", "password": "motdepasse123"}
        ).json()
    )
    assert data_client.get("/v1/admin/ingestion-runs", headers=h).status_code == 200
    assert data_client.post("/v1/admin/catalog/sync", headers=h).json()["components"] >= 40
    assert "correction_rate" in data_client.get("/v1/admin/feedback-stats", headers=h).json()


def test_rgpd_export_and_erasure(data_client):
    h = auth(register_and_login(data_client, email="moi@example.org"))
    data_client.post("/v1/inventory", json={"component_id": "led", "quantity": 3}, headers=h)
    export = data_client.get("/v1/users/me/export", headers=h).json()
    assert export["compte"]["email"] == "moi@example.org"
    assert export["inventaire"][0]["component_id"] == "led"
    assert data_client.delete("/v1/users/me", headers=h).status_code == 204
    assert data_client.get("/v1/users/me", headers=h).status_code == 401


def test_rate_limit_on_token(data_client, monkeypatch):
    from microforge.common.settings import get_settings

    monkeypatch.setenv("MF_RATE_LIMIT_TOKEN", "2/minute")
    get_settings.cache_clear()
    codes = [
        data_client.post("/v1/auth/token", data={"username": "x", "password": "y"}).status_code
        for _ in range(4)
    ]
    assert 429 in codes
