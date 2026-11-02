"""Types partagés."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["text", "code", "vision", "embed"]


@dataclass(frozen=True)
class ImageInput:
    """Image envoyée à un modèle vision."""

    data: bytes
    media_type: str = "image/jpeg"


@dataclass
class ChatRequest:
    """Requête normalisée, indépendante du fournisseur."""

    prompt: str
    role: Role = "text"
    system: str | None = None
    images: list[ImageInput] = field(default_factory=list)
    json_schema: dict[str, Any] | None = None
    schema_name: str = "reponse"
    max_tokens: int = 4096
    temperature: float | None = 0.2


@dataclass
class ChatResult:
    """Réponse normalisée."""

    text: str
    provider: str
    model: str
    latency_s: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    fallback_from: list[str] = field(default_factory=list)
