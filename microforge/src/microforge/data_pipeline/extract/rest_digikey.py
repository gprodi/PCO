"""Source REST n°1 — DigiKey Product Information API v4 (OAuth2 client credentials).

Contraintes identifiées (à documenter dans docs/E1/specifications.md) :
* compte développeur gratuit, application « Production » ; client_id / client_secret dans .env ;
* quotas par minute et par jour (voir le portail développeur) -> pagination prudente, cache ;
* paramètres de locale : site FR, devise EUR ;
* CGU : usage des données limité à l'affichage de prix et de caractéristiques.
"""

from __future__ import annotations

import os
from typing import Any

from microforge.data_pipeline.base import ExtractionError, Extractor, RawPart, to_dict
from microforge.data_pipeline.extract._http import http_retry, make_client

TOKEN_URL = "https://api.digikey.com/v1/oauth2/token"  # noqa: S105 — URL, pas un secret
SEARCH_URL = "https://api.digikey.com/products/v4/search/keyword"
DEFAULT_KEYWORDS = [
    "DHT22",
    "SSD1306 OLED",
    "HC-SR04",
    "BME280",
    "SG90 servo",
    "ESP32-DevKitC",
    "MPU-6050",
    "WS2812B ring",
]


class DigiKeyExtractor(Extractor):
    source = "digikey"
    kind = "rest"

    def setup(self) -> None:
        self.client_id = self.params.get("client_id") or os.getenv("DIGIKEY_CLIENT_ID")
        self.client_secret = self.params.get("client_secret") or os.getenv("DIGIKEY_CLIENT_SECRET")
        if not (self.client_id and self.client_secret):
            raise ExtractionError("DIGIKEY_CLIENT_ID / DIGIKEY_CLIENT_SECRET manquants")
        self.http = self.params.get("http") or make_client()
        self.token = self._token()

    @http_retry
    def _token(self) -> str:
        resp = self.http.post(
            TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    @http_retry
    def _search(self, keyword: str, limit: int, offset: int) -> dict[str, Any]:
        resp = self.http.post(
            SEARCH_URL,
            json={"Keywords": keyword, "Limit": limit, "Offset": offset},
            headers={
                "Authorization": f"Bearer {self.token}",
                "X-DIGIKEY-Client-Id": self.client_id,
                "X-DIGIKEY-Locale-Site": "FR",
                "X-DIGIKEY-Locale-Language": "fr",
                "X-DIGIKEY-Locale-Currency": "EUR",
            },
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def parse(product: dict[str, Any], keyword: str) -> RawPart:
        params = {p.get("ParameterText"): p.get("ValueText") for p in product.get("Parameters", [])}
        variation = (product.get("ProductVariations") or [{}])[0]
        pricing = variation.get("StandardPricing") or []
        unit = product.get("UnitPrice") or (pricing[0]["UnitPrice"] if pricing else None)
        desc = product.get("Description") or {}
        return RawPart(
            source="digikey",
            source_ref=variation.get("DigiKeyProductNumber")
            or product.get("ManufacturerProductNumber", ""),
            name=desc.get("ProductDescription"),
            mpn=product.get("ManufacturerProductNumber"),
            manufacturer=(product.get("Manufacturer") or {}).get("Name"),
            description=desc.get("DetailedDescription"),
            category=(product.get("Category") or {}).get("Name"),
            package=params.get("Package / Case") or params.get("Supplier Device Package"),
            supply_text=params.get("Voltage - Supply") or params.get("Tension - Alimentation"),
            interfaces_text=params.get("Interface") or params.get("Output Type"),
            price=unit,
            currency="EUR",
            stock=product.get("QuantityAvailable"),
            url=product.get("ProductUrl"),
            datasheet_url=product.get("DatasheetUrl"),
            supplier="DigiKey",
            extra={"keyword": keyword, "price_breaks": pricing},
        )

    def extract(self) -> list[dict[str, Any]]:
        keywords = self.params.get("keywords") or DEFAULT_KEYWORDS
        limit = int(self.params.get("limit", 10))
        records = []
        for kw in keywords:
            data = self._search(kw, limit, 0)
            records += [to_dict(self.parse(p, kw)) for p in data.get("Products", [])]
        return records
