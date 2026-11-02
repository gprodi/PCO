"""Source REST n°3 — API GitHub : qualité des bibliothèques Arduino (étoiles, activité, licence).

Contrainte : 60 req/h anonymes, 5 000 req/h avec ``GITHUB_TOKEN`` (jeton en lecture seule).
"""

from __future__ import annotations

import os
from typing import Any

from microforge.data_pipeline.base import Extractor
from microforge.data_pipeline.extract._http import http_retry, make_client

SEARCH_URL = "https://api.github.com/search/repositories"


class GitHubLibrariesExtractor(Extractor):
    source = "github"
    kind = "rest"

    def setup(self) -> None:
        token = self.params.get("token") or os.getenv("GITHUB_TOKEN")
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.http = self.params.get("http") or make_client(headers=headers)

    @http_retry
    def _search(self, query: str) -> dict[str, Any]:
        resp = self.http.get(
            SEARCH_URL, params={"q": query, "sort": "stars", "order": "desc", "per_page": 10}
        )
        resp.raise_for_status()
        return resp.json()

    def extract(self) -> list[dict[str, Any]]:
        out = []
        for lib in self.params.get("libraries") or [
            "DHT sensor library",
            "Adafruit SSD1306",
            "ESP32Servo",
            "RTClib",
        ]:
            data = self._search(f'"{lib}" in:name,description topic:arduino-library')
            for item in data.get("items", [])[:3]:
                out.append(
                    {
                        "library": lib,
                        "repository": item.get("full_name"),
                        "url": item.get("html_url"),
                        "stars": item.get("stargazers_count"),
                        "pushed_at": item.get("pushed_at"),
                        "license": (item.get("license") or {}).get("spdx_id"),
                        "archived": item.get("archived", False),
                    }
                )
        return out
