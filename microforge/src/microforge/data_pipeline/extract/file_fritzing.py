"""Source fichier n°2 — pièces Fritzing (``.fzp`` XML, licence CC-BY-SA) : brochages de modules.

Usage : ``git clone --depth 1 https://github.com/fritzing/fritzing-parts`` puis
``mf-pipeline extract fritzing --path fritzing-parts/core``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lxml import etree

from microforge.data_pipeline.base import ExtractionError, Extractor


def parse_fzp(content: bytes) -> dict[str, Any]:
    root = etree.fromstring(
        content, parser=etree.XMLParser(resolve_entities=False, no_network=True)
    )
    props = {p.get("name", "").lower(): (p.text or "").strip() for p in root.iter("property")}
    connectors = [
        {
            "id": c.get("id"),
            "name": c.get("name"),
            "description": (c.findtext("description") or "").strip(),
        }
        for c in root.iter("connector")
    ]
    return {
        "module_id": root.get("moduleId"),
        "title": (root.findtext("title") or "").strip(),
        "family": props.get("family"),
        "properties": props,
        "tags": [t.text for t in root.iter("tag") if t.text],
        "connectors": connectors,
    }


class FritzingExtractor(Extractor):
    source = "fritzing"
    kind = "file"

    def extract(self) -> list[dict[str, Any]]:
        base = Path(self.params.get("path", "fritzing-parts/core"))
        if not base.exists():
            raise ExtractionError(f"Dossier Fritzing introuvable : {base}")
        keywords = [
            k.lower()
            for k in self.params.get(
                "keywords",
                [
                    "sensor",
                    "display",
                    "servo",
                    "esp32",
                    "arduino",
                    "relay",
                    "dht",
                    "oled",
                    "ultrasonic",
                ],
            )
        ]
        out = []
        for fzp in sorted(base.rglob("*.fzp")):
            try:
                part = parse_fzp(fzp.read_bytes())
            except etree.XMLSyntaxError:
                continue  # fichier corrompu : ignoré (compté dans le rapport C3)
            haystack = " ".join([part["title"], part.get("family") or "", *part["tags"]]).lower()
            if any(k in haystack for k in keywords):
                part["file"] = fzp.name
                out.append(part)
        return out
