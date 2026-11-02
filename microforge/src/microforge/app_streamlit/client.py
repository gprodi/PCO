"""Client des deux API, avec renouvellement automatique du jeton d'accès (C10).

Toute la logique métier reste dans les API : l'interface ne fait qu'appeler et afficher
(découplage strict demandé dans les briefs du formateur).
"""

from __future__ import annotations

import os
from typing import Any

import httpx

API_DATA = os.getenv("MF_API_DATA_URL", "http://localhost:8000")
API_IA = os.getenv("MF_API_IA_URL", "http://localhost:8001")


class ApiError(RuntimeError):
    def __init__(self, status: int, detail: Any) -> None:
        super().__init__(f"{status} : {detail}")
        self.status = status
        self.detail = detail


class MicroForgeClient:
    """Conserve la paire de jetons et rejoue une requête après rafraîchissement si 401."""

    def __init__(
        self,
        data_url: str = API_DATA,
        ia_url: str = API_IA,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.data = httpx.Client(base_url=data_url, timeout=30, transport=transport)
        self.ia = httpx.Client(base_url=ia_url, timeout=300, transport=transport)
        self.access: str | None = None
        self.refresh_token: str | None = None

    # ------------------------------------------------------------------ authentification
    @property
    def logged_in(self) -> bool:
        return self.access is not None

    def register(
        self, username: str, email: str, password: str, city: str | None, consent: bool
    ) -> dict:
        return self._check(
            self.data.post(
                "/v1/auth/register",
                json={
                    "username": username,
                    "email": email,
                    "password": password,
                    "city": city or None,
                    "consent_training": consent,
                },
            )
        )

    def login(self, username: str, password: str) -> None:
        tokens = self._check(
            self.data.post("/v1/auth/token", data={"username": username, "password": password})
        )
        self.access, self.refresh_token = tokens["access_token"], tokens["refresh_token"]

    def logout(self) -> None:
        if self.refresh_token:
            self.data.post("/v1/auth/logout", json={"refresh_token": self.refresh_token})
        self.access = self.refresh_token = None

    def _refresh(self) -> bool:
        if not self.refresh_token:
            return False
        resp = self.data.post("/v1/auth/refresh", json={"refresh_token": self.refresh_token})
        if resp.status_code != 200:
            self.access = self.refresh_token = None
            return False
        tokens = resp.json()
        self.access, self.refresh_token = tokens["access_token"], tokens["refresh_token"]
        return True

    # ------------------------------------------------------------------ requêtes
    @staticmethod
    def _check(resp: httpx.Response) -> Any:
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except ValueError:
                detail = resp.text
            raise ApiError(resp.status_code, detail)
        if resp.headers.get("content-type", "").startswith("application/json"):
            return resp.json()
        return resp.content

    def _call(self, client: httpx.Client, method: str, path: str, **kwargs: Any) -> Any:
        headers = {"Authorization": f"Bearer {self.access}"} if self.access else {}
        resp = client.request(method, path, headers=headers, **kwargs)
        if resp.status_code == 401 and self._refresh():  # jeton expiré : on renouvelle et on rejoue
            resp = client.request(
                method, path, headers={"Authorization": f"Bearer {self.access}"}, **kwargs
            )
        return self._check(resp)

    def get(self, path: str, **kw: Any) -> Any:
        return self._call(self.data, "GET", path, **kw)

    def post(self, path: str, **kw: Any) -> Any:
        return self._call(self.data, "POST", path, **kw)

    def delete(self, path: str) -> Any:
        return self._call(self.data, "DELETE", path)

    def ia_post(self, path: str, **kw: Any) -> Any:
        return self._call(self.ia, "POST", path, **kw)

    # ------------------------------------------------------------------ raccourcis métier
    def scan(self, image: bytes, filename: str, mime: str) -> dict:
        return self.ia_post("/v1/vision/scan", files={"image": (filename, image, mime)})

    def inventory_summary(self) -> dict[str, int]:
        return self.get("/v1/inventory/summary")

    def suggest(self, inventory: dict[str, int]) -> list[dict]:
        return self.ia_post("/v1/builds/suggest", json={"inventory": inventory, "limit": 12})

    def generate(
        self, template_id: str | None = None, board: str | None = None, spec: dict | None = None
    ) -> dict:
        return self.ia_post(
            "/v1/builds/generate", json={"template_id": template_id, "board": board, "spec": spec}
        )

    def bundle(
        self, template_id: str | None = None, board: str | None = None, spec: dict | None = None
    ) -> bytes:
        return self.ia_post(
            "/v1/builds/bundle", json={"template_id": template_id, "board": board, "spec": spec}
        )

    def from_goal(
        self,
        goal: str,
        board: str | None,
        inventory: dict[str, int] | None,
        components: list[str] | None = None,
    ) -> dict:
        return self.ia_post(
            "/v1/builds/from-goal",
            json={"goal": goal, "board": board, "inventory": inventory, "components": components},
        )

    def explore(self, inventory: dict[str, int] | None) -> list[dict]:
        """Thèmes et idées de projets, annotés avec le stock."""
        return self.ia_post("/v1/ideas/explore", json={"inventory": inventory})

    def inspiration(self) -> dict:
        """Parcours de progression, vitrine de vrais projets, chiffres clés."""
        return self._call(self.ia, "GET", "/v1/ideas/inspiration")
