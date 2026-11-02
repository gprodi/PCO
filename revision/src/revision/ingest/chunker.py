"""Découpage en passages (chunks) par titres, avec chevauchement, pour le RAG et les citations."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Chunk:
    id: str  # "<slug>#<n>"
    course: str
    heading: str
    text: str


def chunk_markdown(
    slug: str, markdown: str, max_chars: int = 1800, overlap: int = 200
) -> list[Chunk]:
    sections: list[tuple[str, str]] = []
    heading, buf = "Introduction", []
    for line in markdown.splitlines():
        m = re.match(r"^(#{1,4})\s+(.+)", line)
        if m:
            if buf:
                sections.append((heading, "\n".join(buf).strip()))
            heading, buf = m.group(2).strip(), []
        else:
            buf.append(line)
    if buf:
        sections.append((heading, "\n".join(buf).strip()))
    chunks: list[Chunk] = []
    for head, body in sections:
        if not body:
            continue
        start = 0
        while start < len(body):
            piece = body[start : start + max_chars]
            chunks.append(Chunk(id=f"{slug}#{len(chunks)}", course=slug, heading=head, text=piece))
            if start + max_chars >= len(body):
                break
            start += max_chars - overlap
    return chunks
