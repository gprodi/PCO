"""Interface commune des fournisseurs."""

from __future__ import annotations

from abc import ABC, abstractmethod

from llm_gateway.types import ChatRequest, ChatResult


class Provider(ABC):
    """Un fournisseur sait discuter (texte, vision, JSON) et, éventuellement, calculer des embeddings."""

    name: str = "base"
    supports_embeddings: bool = True
    supports_vision: bool = True

    @abstractmethod
    def chat(self, request: ChatRequest, model: str) -> ChatResult:
        """Envoie une requête de chat et renvoie le texte de la réponse."""

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """Calcule des embeddings (non supporté par défaut)."""
        raise NotImplementedError(f"{self.name} ne fournit pas d'embeddings")

    def is_configured(self) -> bool:
        """Le fournisseur a-t-il ce qu'il faut (clé, URL) pour être tenté ?"""
        return True
