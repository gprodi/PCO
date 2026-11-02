"""Outils JSON Schema : schéma « strict » accepté par les sorties structurées des fournisseurs."""

from __future__ import annotations

import copy
import json
import re
from typing import Any

_UNSUPPORTED = {"default", "examples", "title"}


def strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Rend un schéma Pydantic compatible « strict » (Anthropic, OpenAI-compatible).

    * ``additionalProperties: false`` sur chaque objet ;
    * toutes les propriétés deviennent ``required`` ;
    * suppression des mots-clés non supportés (``default``, ``title``, ``examples``).
    """
    out = copy.deepcopy(schema)

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for key in list(node):
                if key in _UNSUPPORTED and not isinstance(node.get(key), dict):
                    node.pop(key)
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"])
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(out)
    return out


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> Any:
    """Extrait le premier objet JSON d'une réponse (tolère les blocs ```json``` et le texte autour)."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = _FENCE.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Les modèles « thinking » locaux peuvent préfixer <think>...</think>
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("Aucun JSON valide dans la réponse du modèle")


def example_from_schema(schema: dict[str, Any], root: dict[str, Any] | None = None) -> Any:
    """Construit une instance minimale valide d'un schéma (utilisé par le FakeProvider)."""
    root = root or schema
    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        return example_from_schema(root.get("$defs", {}).get(name, {}), root)
    for key in ("anyOf", "oneOf", "allOf"):
        if key in schema:
            options = [s for s in schema[key] if s.get("type") != "null"] or schema[key]
            return example_from_schema(options[0], root)
    if "enum" in schema:
        return schema["enum"][0]
    if "const" in schema:
        return schema["const"]
    typ = schema.get("type")
    if isinstance(typ, list):
        typ = next((t for t in typ if t != "null"), "null")
    if typ == "object":
        return {k: example_from_schema(v, root) for k, v in schema.get("properties", {}).items()}
    if typ == "array":
        n = max(1, schema.get("minItems", 1))
        return [example_from_schema(schema.get("items", {}), root) for _ in range(n)]
    if typ == "string":
        return "exemple"
    if typ == "integer":
        return int(schema.get("minimum", 1))
    if typ == "number":
        return float(schema.get("minimum", 1.0))
    if typ == "boolean":
        return True
    return None
