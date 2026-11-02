"""Source REST n°2 — Mouser Search API (clé d'API gratuite, mouser.com/api-hub).

Contrainte : quota non publié -> 1 requête/s côté client et relance exponentielle sur 429.
Particularité utile pour C3 : les prix arrivent en texte localisé (« 3,50 € »).
"""

from __future__ import annotations

import os
import re
import time
from typing import Any

from microforge.data_pipeline.base import ExtractionError, Extractor, RawPart, to_dict
from microforge.data_pipeline.extract._http import http_retry, make_client
from microforge.data_pipeline.extract.rest_digikey import DEFAULT_KEYWORDS

SEARCH_URL = "https://api.mouser.com/api/v1/search/keyword"


class MouserExtractor(Extractor):
    source = "mouser"
    kind = "rest"

    def setup(self) -> None:
        self.api_key = self.params.get("api_key") or os.getenv("MOUSER_API_KEY")
        if not self.api_key:
            raise ExtractionError("MOUSER_API_KEY manquante")
        self.http = self.params.get("http") or make_client()
        self.delay = float(self.params.get("delay_s", 1.0))

    @http_retry
    def _search(self, keyword: str, records: int) -> dict[str, Any]:
        resp = self.http.post(
            SEARCH_URL,
            params={"apiKey": self.api_key},
            json={
                "SearchByKeywordRequest": {
                    "keyword": keyword,
                    "records": records,
                    "startingRecord": 0,
                }
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("Errors"):
            raise ExtractionError(f"Mouser : {data['Errors']}")
        return data

    @staticmethod
    def parse(part: dict[str, Any], keyword: str) -> RawPart:
        breaks = part.get("PriceBreaks") or []
        first = breaks[0] if breaks else {}
        availability = part.get("Availability") or ""
        m = re.search(r"\d[\d\s.]*", availability)
        return RawPart(
            source="mouser",
            source_ref=part.get("MouserPartNumber") or part.get("ManufacturerPartNumber", ""),
            name=part.get("Description"),
            mpn=part.get("ManufacturerPartNumber"),
            manufacturer=part.get("Manufacturer"),
            description=part.get("Description"),
            category=part.get("Category"),
            price=first.get("Price"),
            currency=first.get("Currency"),
            stock=m.group(0) if m else None,
            url=part.get("ProductDetailUrl"),
            datasheet_url=part.get("DataSheetUrl"),
            supplier="Mouser",
            extra={"keyword": keyword, "price_breaks": breaks},
        )

    def extract(self) -> list[dict[str, Any]]:
        out = []
        for kw in self.params.get("keywords") or DEFAULT_KEYWORDS:
            data = self._search(kw, int(self.params.get("limit", 10)))
            out += [
                to_dict(self.parse(p, kw))
                for p in (data.get("SearchResults") or {}).get("Parts", [])
            ]
            time.sleep(self.delay)
        return out
