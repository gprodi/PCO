"""Tests du client de la preuve de concept : renouvellement automatique du jeton (C10)."""

from __future__ import annotations

import httpx
import pytest
from microforge.app_streamlit.client import ApiError, MicroForgeClient


def test_refresh_then_replay_on_401():
    state = {"access": "a1", "refresh_calls": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path == "/v1/auth/token":
            return httpx.Response(200, json={"access_token": "a1", "refresh_token": "r1"})
        if path == "/v1/auth/refresh":
            state["refresh_calls"] += 1
            state["access"] = "a2"
            return httpx.Response(200, json={"access_token": "a2", "refresh_token": "r2"})
        if path == "/v1/users/me":
            if (
                req.headers.get("authorization") != f"Bearer {state['access']}"
                or state["access"] == "a1"
            ):
                state["access"] = "expired"
                return httpx.Response(401, json={"detail": "expiré"})
            return httpx.Response(200, json={"username": "gael"})
        return httpx.Response(404, json={"detail": "inconnu"})

    c = MicroForgeClient("http://data", "http://ia", transport=httpx.MockTransport(handler))
    c.login("gael", "x")
    assert c.get("/v1/users/me") == {"username": "gael"}
    assert state["refresh_calls"] == 1 and c.refresh_token == "r2"


def test_errors_and_logout():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/v1/auth/refresh":
            return httpx.Response(401, json={"detail": "révoqué"})
        if req.url.path == "/v1/auth/logout":
            return httpx.Response(204)
        return httpx.Response(401, json={"detail": "non"})

    c = MicroForgeClient("http://data", "http://ia", transport=httpx.MockTransport(handler))
    c.access, c.refresh_token = "a", "r"
    with pytest.raises(ApiError) as err:
        c.get("/v1/inventory")
    assert err.value.status == 401 and not c.logged_in
    c.refresh_token = "r"
    c.logout()
    assert c.refresh_token is None


def test_explore_inspiration_and_goal_with_components():
    seen: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen[req.url.path] = req.content
        if req.url.path == "/v1/auth/token":
            return httpx.Response(200, json={"access_token": "a", "refresh_token": "r"})
        if req.url.path == "/v1/ideas/inspiration":
            return httpx.Response(200, json={"parcours": [], "vitrine": [], "chiffres": {}})
        return httpx.Response(200, json=[] if "explore" in req.url.path else {"spec": {}})

    c = MicroForgeClient("http://data", "http://ia", transport=httpx.MockTransport(handler))
    c.login("gael", "x")
    assert c.explore({"led": 1}) == []
    assert c.inspiration()["parcours"] == []
    c.from_goal("Alarme de cave", None, None, ["water-level-sensor", "buzzer"])
    assert b"water-level-sensor" in seen["/v1/builds/from-goal"]
