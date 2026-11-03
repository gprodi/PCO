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

from microforge.core.models import (
    BoardDef,
    BoardPin,
    ComponentDef,
    FamilyDef,
    ProjectTemplate,
    Reference,
)

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
            pin = {
                "gpio": n,
                "label": rng["label"].format(n=n, a=a),
                "wokwi": rng.get("wokwi", "{n}").format(n=n, a=a),
                "caps": rng.get("caps", ["digital"]),
            }
            for flag in ("input_only", "strapping", "reserved", "note"):
                if flag in rng:
                    pin[flag] = rng[flag]
            pins.append(pin)
    gpios = [p["gpio"] for p in pins]
    dup = sorted({g for g in gpios if gpios.count(g) > 1})
    if dup:
        raise ValueError(f"Carte {raw.get('id')} : GPIO en double {dup}")
    raw["pins"] = pins
    return raw


class Catalog:
    """Accès indexé aux composants, cartes et modèles de projets."""

    def __init__(
        self,
        components: list[ComponentDef],
        boards: list[BoardDef],
        templates: list[ProjectTemplate],
        families: list[FamilyDef] | None = None,
    ) -> None:
        self.components = {c.id: c for c in components}
        self.boards = {b.id: b for b in boards}
        self.templates = {t.id: t for t in templates}
        if families is None:
            families = [FamilyDef.model_validate(f) for f in _read_yaml("families.yaml")]
        self.families = {f.id: f for f in families}
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
        boards: list[BoardDef] = []
        board_dir = resources.files(_DATA).joinpath("boards")
        for entry in sorted(board_dir.iterdir(), key=lambda p: p.name):
            if entry.name.endswith(".yaml"):
                for raw in yaml.safe_load(entry.read_text(encoding="utf-8")):
                    boards.append(BoardDef.model_validate(_expand_board(raw)))
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

    # ------------------------------------------------------------------ familles et compatibilité
    def representative(self, family: str) -> BoardDef:
        """Carte de référence d'une famille (tests, CI) : la première marquée ``representative``."""
        boards = [b for b in self.boards.values() if b.family == family]
        return next((b for b in boards if b.representative), boards[0])

    def template_families(self, template_id: str) -> list[str]:
        """Familles compatibles avec un modèle : intersection des familles de ses composants,
        de sa restriction éventuelle et, s'il exige le Wi-Fi, des familles où il est géré."""
        tpl = self.templates[template_id]
        fams = set(self.families)
        if tpl.board_families:
            fams &= set(tpl.board_families)
        for part in tpl.parts:
            comp = self.components.get(self.resolve(part.component) or part.component)
            if comp is not None:
                fams = {f for f in fams if comp.supports_family(f)}
        if tpl.requires_wifi:
            fams &= {f for f, d in self.families.items() if d.wifi_supported}
        order = list(self.families)
        return sorted(fams, key=order.index)

    def template_fits(self, template_id: str, board: BoardDef) -> bool:
        tpl = self.templates[template_id]
        return (
            board.family in self.template_families(template_id)
            and (board.wifi or not tpl.requires_wifi)
            and all(
                comp.supports(board)
                for part in tpl.parts
                if (comp := self.components.get(self.resolve(part.component) or part.component))
            )
        )

    def boards_for_template(self, template_id: str) -> list[BoardDef]:
        return [b for b in self.boards.values() if self.template_fits(template_id, b)]

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
        if getattr(self, "_aliases_sorted", None) is None or len(self._aliases_sorted) != len(
            self._aliases
        ):  # cache : appelée des dizaines de milliers de fois par l'agrégation (C3)
            self._aliases_sorted = sorted(self._aliases, key=len, reverse=True)
        for alias in self._aliases_sorted:
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
