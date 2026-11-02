"""Ingestion : n'importe quel support de cours -> Markdown normalisé + découpage en passages."""

from revision.ingest.chunker import Chunk, chunk_markdown
from revision.ingest.converters import SUPPORTED, convert_file, convert_url

__all__ = ["SUPPORTED", "Chunk", "chunk_markdown", "convert_file", "convert_url"]
