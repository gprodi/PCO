"""Source REST n°4 — taux de change pour normaliser les prix en EUR (C3).

1. **Frankfurter** (taux de référence BCE, sans clé) ;
2. repli si l'API est injoignable : jeu ouvert ``datasets/exchange-rates`` (taux quotidiens de la
   Réserve fédérale, série H.10, publiés en CSV sur GitHub ; colonnes ``Date,Country,Exchange rate`` =
   unités de devise pour 1 USD). Le manifeste indique la source réellement utilisée.
"""

from __future__ import annotations

import csv
import io
from typing import Any

import httpx
from loguru import logger

from microforge.data_pipeline.base import ExtractionError, Extractor
from microforge.data_pipeline.extract._http import http_retry, make_client

FX_URL = "https://api.frankfurter.app/latest"
FED_CSV_URL = "https://raw.githubusercontent.com/datasets/exchange-rates/main/data/daily.csv"
FED_COUNTRY = {"EUR": "Euro", "CNY": "China", "GBP": "United Kingdom", "CHF": "Switzerland"}


def rates_from_fed_csv(text: str, symbols: list[str]) -> list[dict[str, Any]]:
    """« unités par USD » (dernière date où l'euro est publié) -> « EUR pour 1 unité »."""
    latest: dict[str, tuple[str, float]] = {}
    for row in csv.DictReader(io.StringIO(text)):
        try:
            value = float(row["Exchange rate"])
        except (KeyError, TypeError, ValueError):
            continue  # ligne vide ou corrompue (jours fériés publiés sans valeur)
        country, day = row.get("Country"), row.get("Date") or ""
        if value > 0 and (country not in latest or day >= latest[country][0]):
            latest[country] = (day, value)
    if "Euro" not in latest:
        raise ExtractionError("CSV H.10 sans cours de l'euro")
    day, eur_per_usd = latest["Euro"]
    out = [{"currency": "USD", "eur_per_unit": round(eur_per_usd, 6), "date": day}]
    for cur in symbols:
        country = FED_COUNTRY.get(cur)
        if cur in ("USD", "EUR") or country not in latest:
            continue
        cday, per_usd = latest[country]
        out.append({"currency": cur, "eur_per_unit": round(eur_per_usd / per_usd, 6), "date": cday})
    return [*out, {"currency": "EUR", "eur_per_unit": 1.0, "date": day}]


class FrankfurterExtractor(Extractor):
    source = "fx"
    kind = "rest"

    def setup(self) -> None:
        self.http = self.params.get("http") or make_client()
        self.symbols = [
            s.strip() for s in self.params.get("symbols", "USD,CNY,GBP,CHF").split(",") if s.strip()
        ]

    @http_retry
    def _frankfurter(self) -> list[dict[str, Any]]:
        resp = self.http.get(
            self.params.get("url", FX_URL), params={"from": "EUR", "to": ",".join(self.symbols)}
        )
        resp.raise_for_status()
        data = resp.json()
        # Taux « 1 EUR = x devise » -> on stocke « 1 devise = y EUR » pour la conversion.
        return [
            {"currency": cur, "eur_per_unit": round(1 / rate, 6), "date": data["date"]}
            for cur, rate in data["rates"].items()
        ] + [{"currency": "EUR", "eur_per_unit": 1.0, "date": data["date"]}]

    @http_retry
    def _fed(self) -> list[dict[str, Any]]:
        resp = self.http.get(self.params.get("fallback_url", FED_CSV_URL), timeout=60)
        resp.raise_for_status()
        return rates_from_fed_csv(resp.text, self.symbols)

    def extract(self) -> list[dict[str, Any]]:
        try:
            rows = self._frankfurter()
            self.params["provider"] = "frankfurter (BCE)"
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning("Frankfurter injoignable ({}) : repli sur la série H.10", exc)
            rows = self._fed()
            self.params["provider"] = "datasets/exchange-rates (Fed H.10)"
        return rows
