"""Fournisseur déterministe pour les tests, la CI et les démos hors ligne (``LLM_CHAIN=fake``)."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from typing import Any

from llm_gateway.providers.base import Provider
from llm_gateway.schema_utils import example_from_schema
from llm_gateway.types import ChatRequest, ChatResult

Responder = Callable[[ChatRequest], str | dict | list]


class FakeProvider(Provider):
    """Répond à partir de règles « mot-clé -> réponse », sinon génère une réponse valide du schéma.

    Exemple ::

        fake = FakeProvider({"DHT22": {"reference": "DHT22", "categorie": "capteur"}})
    """

    name = "fake"

    def __init__(
        self,
        rules: dict[str, Any] | None = None,
        default_text: str = "Réponse simulée (FakeProvider).",
        responder: Responder | None = None,
        embed_dim: int = 64,
        fail: bool = False,
    ) -> None:
        self.rules = rules or {}
        self.default_text = default_text
        self.responder = responder
        self.embed_dim = embed_dim
        self.fail = fail
        self.calls: list[ChatRequest] = []

    def chat(self, request: ChatRequest, model: str) -> ChatResult:
        from llm_gateway.errors import ProviderUnavailableError

        self.calls.append(request)
        if self.fail:
            raise ProviderUnavailableError("fake : panne simulée")
        answer: Any = None
        if self.responder is not None:
            answer = self.responder(request)
        if answer is None:
            for keyword, value in self.rules.items():
                if keyword.lower() in request.prompt.lower():
                    answer = value
                    break
        if answer is None:
            answer = (
                example_from_schema(request.json_schema)
                if request.json_schema is not None
                else self.default_text
            )
        text = answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)
        return ChatResult(text=text, provider=self.name, model=model or "fake-model")

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """Embeddings par hachage de mots : déterministes, et proches pour des textes proches."""
        vectors = []
        for text in texts:
            vec = [0.0] * self.embed_dim
            for word in text.lower().split():
                h = int(hashlib.md5(word.encode(), usedforsecurity=False).hexdigest(), 16)
                vec[h % self.embed_dim] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors
