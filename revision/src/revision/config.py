"""Chemins et configuration du site de révision."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]  # racine du dépôt PCO


@dataclass(frozen=True)
class Paths:
    root: Path = ROOT
    cours: Path = ROOT / "cours"
    revision: Path = ROOT / "revision"
    content: Path = ROOT / "revision" / "content"
    seed: Path = ROOT / "revision" / "seed"
    index: Path = ROOT / "revision" / "content" / "_index.json"
    site_data: Path = ROOT / "revision" / "site" / "src" / "data"
    referentiel: Path = ROOT / "referentiel" / "referentiel.yaml"
    boilerplates: Path = ROOT / "revision" / "boilerplates"


PATHS = Paths()


@lru_cache(maxsize=1)
def registry() -> dict:
    return yaml.safe_load((PATHS.revision / "courses.yaml").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def referentiel() -> dict:
    return yaml.safe_load(PATHS.referentiel.read_text(encoding="utf-8"))
