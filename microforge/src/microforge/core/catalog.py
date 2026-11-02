"""Catalogue : composants, cartes et modèles de projets chargés depuis ``core/data/*.yaml``.

Le catalogue est la « vérité terrain » de MicroForge : le LLM ne peut proposer que des composants
qui existent ici, et l'allocateur ne câble que des broches décrites ici. Le pipeline E1 l'enrichit
(prix, brochages Fritzing, bibliothèques Arduino) via la base PostgreSQL.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from importlib import resources
from typing import Any

import yaml

from microforge.core.models import BoardDef, BoardPin, ComponentDef, ProjectTemplate, Reference

_DATA = "microforge.core.data"


def normalize(text: str) -> str:
    """Normalise un nom pour la recherche : minuscules, sans accents ni ponctuation."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _read_yaml(*parts: str) -> Any:
    path = resources.files(_DATA).joinpath(*parts)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _expand_board(raw: dict[str, Any]) -> dict[str, Any]:
    """Développe les ``pin_ranges`` (Mega, Pico) en liste de broches."""
    pins = list(raw.get("pins") or [])
    for rng in raw.pop("pin_ranges", []) or []:
        offset = rng.get("analog_offset", 0)
        for n in range(rng["from"], rng["to"] + 1):
            a = n - offset
            pins.append(
                {
                    "gpio": n,
                    "label": rng["label"].format(n=n, a=a),
                    "wokwi": rng.get("wokwi", "{n}").format(n=n, a=a),
                    "caps": rng.get("caps", ["digital"]),
                }
            )
    raw["pins"] = pins
    return raw


class Catalog:
    """Accès indexé aux composants, cartes et modèles de projets."""

    def __init__(
        self,
        components: list[ComponentDef],
        boards: list[BoardDef],
        templates: list[ProjectTemplate],
    ) -> None:
        self.components = {c.id: c for c in components}
        self.boards = {b.id: b for b in boards}
        self.templates = {t.id: t for t in templates}
        self._aliases: dict[str, str] = {}
        for item in [*components, *boards]:
            for key in [item.id, item.name, *item.aliases]:
                self._aliases.setdefault(normalize(key), item.id)

    # ------------------------------------------------------------------ chargement
    @classmethod
    def load(cls) -> Catalog:
        """Charge le catalogue embarqué dans le paquet."""
        components: list[ComponentDef] = []
        comp_dir = resources.files(_DATA).joinpath("components")
        for entry in sorted(comp_dir.iterdir(), key=lambda p: p.name):
            if entry.name.endswith(".yaml"):
                for raw in yaml.safe_load(entry.read_text(encoding="utf-8")):
                    components.append(ComponentDef.model_validate(raw))
        boards = [BoardDef.model_validate(_expand_board(b)) for b in _read_yaml("boards.yaml")]
        templates: list[ProjectTemplate] = []
        proj_dir = resources.files(_DATA).joinpath("projects")
        for entry in sorted(proj_dir.iterdir(), key=lambda p: p.name):
            if entry.name.endswith(".yaml"):
                for raw in yaml.safe_load(entry.read_text(encoding="utf-8")):
                    templates.append(ProjectTemplate.model_validate(raw))
        refs = (
            yaml.safe_load(
                resources.files(_DATA).joinpath("references.yaml").read_text(encoding="utf-8")
            )
            or {}
        )
        for tpl in templates:
            tpl.references = [Reference.model_validate(r) for r in refs.get(tpl.id, [])]
        return cls(components, boards, templates)

    # ------------------------------------------------------------------ accès
    def component(self, ref: str) -> ComponentDef:
        """Composant par identifiant ou alias."""
        key = self.resolve(ref)
        if key is None or key not in self.components:
            raise KeyError(f"Composant inconnu : {ref!r}")
        return self.components[key]

    def board(self, ref: str) -> BoardDef:
        """Carte par identifiant ou alias."""
        key = self.resolve(ref)
        if key is None or key not in self.boards:
            raise KeyError(f"Carte inconnue : {ref!r}")
        return self.boards[key]

    def is_board(self, ref: str) -> bool:
        return self.resolve(ref) in self.boards

    def resolve(self, ref: str) -> str | None:
        """Identifiant canonique à partir d'un id, d'un nom ou d'un alias (ex. « oled » -> ssd1306-i2c)."""
        if ref in self.components or ref in self.boards:
            return ref
        return self._aliases.get(normalize(ref))

    def resolve_fuzzy(self, text: str) -> str | None:
        """Résolution tolérante d'un libellé libre (ex. « carte ESP32 » -> esp32-devkit-v1).

        On cherche l'alias le plus long contenu, mot pour mot, dans le libellé.
        """
        exact = self.resolve(text)
        if exact:
            return exact
        padded = f" {normalize(text)} "
        for alias in sorted(self._aliases, key=len, reverse=True):
            if len(alias) >= 3 and f" {alias} " in padded:
                return self._aliases[alias]
        return None

    def search(self, query: str, limit: int = 10) -> list[ComponentDef | BoardDef]:
        """Recherche plein texte simple (id, nom, alias, description)."""
        q = normalize(query)
        words = q.split()
        scored: list[tuple[int, ComponentDef | BoardDef]] = []
        for item in [*self.components.values(), *self.boards.values()]:
            haystack = normalize(
                " ".join([item.id, item.name, *item.aliases, getattr(item, "description", "")])
            )
            score = sum(3 if w in normalize(item.id) else 1 for w in words if w in haystack)
            if score:
                scored.append((score, item))
        scored.sort(key=lambda t: (-t[0], t[1].id))
        return [item for _, item in scored[:limit]]

    def pin_of(self, board: BoardDef, gpio: int) -> BoardPin:
        return board.pin(gpio)


@lru_cache(maxsize=1)
def get_catalog() -> Catalog:
    """Catalogue partagé (chargé une seule fois)."""
    return Catalog.load()
