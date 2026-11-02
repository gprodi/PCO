"""Source REST n°4 — Frankfurter (taux de change BCE, sans clé) : normalisation des prix en EUR (C3)."""

from __future__ import annotations

from typing import Any

from microforge.data_pipeline.base import Extractor
from microforge.data_pipeline.extract._http import http_retry, make_client

FX_URL = "https://api.frankfurter.app/latest"


class FrankfurterExtractor(Extractor):
    source = "fx"
    kind = "rest"

    def setup(self) -> None:
        self.http = self.params.get("http") or make_client()

    @http_retry
    def extract(self) -> list[dict[str, Any]]:
        symbols = self.params.get("symbols", "USD,CNY,GBP,CHF")
        resp = self.http.get(self.params.get("url", FX_URL), params={"from": "EUR", "to": symbols})
        resp.raise_for_status()
        data = resp.json()
        # Taux « 1 EUR = x devise » -> on stocke « 1 devise = y EUR » pour la conversion.
        return [
            {"currency": cur, "eur_per_unit": round(1 / rate, 6), "date": data["date"]}
            for cur, rate in data["rates"].items()
        ] + [{"currency": "EUR", "eur_per_unit": 1.0, "date": data["date"]}]
