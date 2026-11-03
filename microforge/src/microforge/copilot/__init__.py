"""Copilote RAG de MicroForge : répond aux questions sur le matériel en citant le catalogue."""

from microforge.copilot.corpus import build_corpus, fingerprint
from microforge.copilot.service import Copilot, CopilotAnswer, Source, make_copilot

__all__ = ["Copilot", "CopilotAnswer", "Source", "build_corpus", "fingerprint", "make_copilot"]
