"""Source fichier n°3 — catalogue LCSC/JLCPCB publié en fichiers JSONL compressés (projet jlcparts).

Le projet open source jlcparts (licence MIT) republie chaque nuit le catalogue en stock de JLCPCB/LCSC
(≈ 370 000 références) sous forme de fichiers statiques : un ``manifest.json`` (catégories, fichiers,
empreintes SHA-256), une table d'attributs ``attributes-lut.json.gz`` et un fichier ``.jsonl.gz`` par
tranche de 1 000 composants. Aucune clé ni scraping : de simples fichiers versionnés sur GitHub.

Traitement :
1. lecture du manifeste et sélection des sous-catégories utiles (``lcsc_categories.yaml``) ;
2. téléchargement de chaque tranche, **contrôle d'intégrité SHA-256** (tranche corrompue = ignorée et
   comptée dans le manifeste) ;
3. décodage des attributs (fabricant, boîtier, résistance, capacité, tension…) et des paliers de prix
   (USD), conversion en enregistrements ``RawPart`` (référence LCSC = ``source_ref``).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from functools import cached_property
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from microforge.data_pipeline.base import ExtractionError, Extractor, RawPart, to_dict
from microforge.data_pipeline.extract._http import http_retry, make_client

BASE_URL = "https://raw.githubusercontent.com/yaqwsx/jlcparts/gh-pages/data/"
UNIT_SYMBOL = {
    "resistance": "Ω",
    "capacitance": "F",
    "voltage": "V",
    "current": "A",
    "power": "W",
    "percentage": "%",
    "temperature": "°C",
    "frequency": "Hz",
    "inductance": "H",
    "time": "s",
}
KEEP_ATTRIBUTES = {
    "Manufacturer",
    "Package",
    "Resistance",
    "Capacitance",
    "Tolerance",
    "Power",
    "Voltage Rated",
    "Supply Voltage (Max)",
    "Operating Voltage",
    "Input Voltage",
    "Output Voltage",
    "Forward Voltage",
    "Current - Continuous Drain(Id)",
    "Collector Current (Ic)",
    "Frequency",
    "Basic/Extended",
    "Status",
    "Type",
    "Color",
}
SI_PREFIX = [
    (1e9, "G"),
    (1e6, "M"),
    (1e3, "k"),
    (1.0, ""),
    (1e-3, "m"),
    (1e-6, "µ"),
    (1e-9, "n"),
    (1e-12, "p"),
]


def si(value: float, unit: str) -> str:
    """4700, Ω -> « 4,7 kΩ » ; 1e-07, F -> « 100 nF »."""
    if value == 0:
        return f"0 {unit}"
    for factor, prefix in SI_PREFIX:
        if abs(value) >= factor * 0.999:
            return f"{value / factor:.3g}".replace(".", ",") + f" {prefix}{unit}"
    return f"{value:.3g} {unit}"


def load_category_map(path: Path | None = None) -> dict[str, str]:
    text = (
        path.read_text(encoding="utf-8")
        if path
        else resources.files("microforge.data_pipeline")
        .joinpath("lcsc_categories.yaml")
        .read_text(encoding="utf-8")
    )
    return yaml.safe_load(text)["categories"]


def decode_attribute(entry: list[Any]) -> tuple[str, str, float | None, str | None]:
    """Entrée de la table d'attributs -> (nom, texte formaté, valeur primaire, grandeur)."""
    name, spec = entry[0], entry[1]
    values = spec.get("values", {})
    text = spec.get("format", "")
    for key, (val, kind) in values.items():
        rendered = (
            si(val, UNIT_SYMBOL[kind])
            if isinstance(val, int | float) and kind in UNIT_SYMBOL
            else str(val)
        )
        text = text.replace("${" + key + "}", rendered)
    primary = values.get(spec.get("primary"), [None, None])
    number = primary[0] if isinstance(primary[0], int | float) else None
    return name, re.sub(r"\s+", " ", text).strip(), number, primary[1]


def unit_price(tiers: list[dict[str, Any]] | None) -> tuple[float | None, int]:
    """Prix unitaire au plus petit palier et quantité minimale de commande."""
    if not tiers:
        return None, 1
    first = min(tiers, key=lambda t: t.get("qFrom") or 1)
    return first.get("price"), int(first.get("qFrom") or 1)


class LcscCatalogExtractor(Extractor):
    source = "lcsc"
    kind = "file"

    def setup(self) -> None:
        self.local = Path(self.params["path"]) if self.params.get("path") else None
        self.http = None if self.local else (self.params.get("http") or make_client(timeout=60))
        self.base_url = self.params.get("base_url", BASE_URL)
        self.categories = self.params.get("categories") or load_category_map()
        self.max_shards = int(self.params.get("max_shards") or 0)  # 0 = toutes les tranches
        self.corrupted: list[str] = []

    @http_retry
    def _download(self, name: str) -> bytes:
        assert self.http is not None
        resp = self.http.get(self.base_url + name)
        resp.raise_for_status()
        return resp.content

    def _read(self, name: str) -> bytes:
        if self.local:
            path = self.local / name
            if not path.exists():
                raise ExtractionError(f"Fichier absent : {path}")
            return path.read_bytes()
        return self._download(name)

    @cached_property
    def manifest(self) -> dict[str, Any]:
        try:
            return json.loads(self._read("manifest.json"))
        except json.JSONDecodeError as exc:
            raise ExtractionError("manifest.json illisible") from exc

    @cached_property
    def lut(self) -> list[Any]:
        name = self.manifest.get("attributesLut", "attributes-lut.json.gz")
        return json.loads(gzip.decompress(self._read(name)))

    def selected(self) -> list[tuple[str, str, dict[str, Any]]]:
        """(nom de la tranche, catégorie MicroForge, entrée de catégorie du manifeste)."""
        out = []
        for cat in self.manifest.get("categories", []):
            key = f"{cat['category']} / {cat.get('subcategory', '')}"
            target = self.categories.get(key)
            if target is None:
                continue
            shards = cat.get("shards", [])
            for shard in shards[: self.max_shards] if self.max_shards else shards:
                out.append((shard, target, cat))
        return out

    def _rows(self, shard: str) -> list[list[Any]] | None:
        data = self._read(shard)
        expected = (self.manifest.get("files", {}).get(shard) or {}).get("sha256")
        if expected and hashlib.sha256(data).hexdigest() != expected:
            self.corrupted.append(shard)
            return None
        lines = gzip.decompress(data).decode("utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def parse(
        self, header: dict[str, int], row: list[Any], target: str, cat: dict
    ) -> dict[str, Any]:
        attrs: dict[str, str] = {}
        value: tuple[float, str] | None = None
        for idx in row[header["attributes"]] or []:
            name, text, number, kind = decode_attribute(self.lut[idx])
            if name in KEEP_ATTRIBUTES:
                attrs[name] = text
            if name in ("Resistance", "Capacitance") and number is not None:
                value = (number, UNIT_SYMBOL[kind])
        price, moq = unit_price(row[header["price"]])
        lcsc = row[header["lcsc"]]
        supply = next(
            (
                attrs[k]
                for k in ("Operating Voltage", "Input Voltage", "Supply Voltage (Max)")
                if k in attrs
            ),
            None,
        )
        return to_dict(
            RawPart(
                source="lcsc",
                source_ref=lcsc,
                name=row[header["description"]],
                mpn=row[header["mfr"]],
                manufacturer=attrs.get("Manufacturer"),
                description=row[header["description"]],
                category=target,
                package=attrs.get("Package"),
                supply_text=supply,
                price=price,
                currency="USD",
                stock=row[header["stock"]],
                url=f"https://www.lcsc.com/product-detail/{lcsc}.html",
                datasheet_url=row[header["datasheet"]],
                supplier="LCSC",
                extra={
                    "match_by_name": False,  # descriptions longues : rapprochement par MPN seulement
                    "lcsc_category": f"{cat['category']} / {cat.get('subcategory', '')}",
                    "attributes": attrs,
                    "value": value[0] if value else None,
                    "value_unit": value[1] if value else None,
                    "value_text": si(*value) if value else None,
                    "moq": moq,
                    "price_tiers": row[header["price"]],
                    "jlc_class": attrs.get("Basic/Extended"),
                },
            )
        )

    def extract(self) -> list[dict[str, Any]]:
        selected = self.selected()
        if not selected:
            raise ExtractionError(
                "Aucune sous-catégorie du manifeste ne correspond à la configuration"
            )
        limit = int(self.params.get("limit") or 0)
        out: list[dict[str, Any]] = []
        for shard, target, cat in selected:
            rows = self._rows(shard)
            if not rows:
                continue
            header, body = rows[0], rows[1:]
            for row in body:
                out.append(self.parse(header, row, target, cat))
                if limit and len(out) >= limit:
                    return out
        self.params["manifest_created"] = self.manifest.get("created")
        self.params["shards"] = len(selected)
        self.params["corrupted_shards"] = self.corrupted
        return out
