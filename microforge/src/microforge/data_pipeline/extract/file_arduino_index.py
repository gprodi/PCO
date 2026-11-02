"""Source fichier n°1 — ``library_index.json`` officiel d'Arduino (~ dizaines de Mo, toutes versions).

Traitement : lecture en flux (fichier local ou téléchargé), conservation de la DERNIÈRE version de
chaque bibliothèque (comparaison sémantique), extraction des ``#include`` fournis.
"""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path
from typing import Any

from microforge.data_pipeline.base import ExtractionError, Extractor
from microforge.data_pipeline.extract._http import make_client

INDEX_URL = "https://downloads.arduino.cc/libraries/library_index.json.gz"


def version_key(version: str) -> tuple[int, ...]:
    """« 1.10.2 » > « 1.9.0 » (comparaison numérique, suffixes ignorés)."""
    return tuple(int(x) for x in re.findall(r"\d+", version)[:4]) or (0,)


class ArduinoIndexExtractor(Extractor):
    source = "arduino_index"
    kind = "file"

    def _load(self) -> dict[str, Any]:
        path = self.params.get("path")
        if path:
            raw = Path(path).read_bytes()
        else:
            with make_client(timeout=120) as http:
                resp = http.get(self.params.get("url", INDEX_URL))
                resp.raise_for_status()
                raw = resp.content
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ExtractionError("library_index.json illisible") from exc

    def extract(self) -> list[dict[str, Any]]:
        data = self._load()
        latest: dict[str, dict[str, Any]] = {}
        for lib in data.get("libraries", []):
            name = lib.get("name")
            if not name or not lib.get("version"):
                continue  # entrée corrompue
            current = latest.get(name)
            if current is None or version_key(lib["version"]) > version_key(current["version"]):
                latest[name] = lib
        wanted = {n.lower() for n in self.params.get("only", [])}
        out = []
        for name, lib in sorted(latest.items()):
            if wanted and name.lower() not in wanted:
                continue
            out.append(
                {
                    "name": name,
                    "version": lib["version"],
                    "author": lib.get("author"),
                    "sentence": lib.get("sentence"),
                    "category": lib.get("category"),
                    "architectures": lib.get("architectures", []),
                    "includes": lib.get("providesIncludes", []),
                    "repository": lib.get("repository") or lib.get("website"),
                    "dependencies": [d.get("name") for d in lib.get("dependencies", [])],
                }
            )
        return out
