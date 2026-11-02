"""Orchestration : cours du registre ou nouvel upload -> source.md + passages -> index -> livrables."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict
from pathlib import Path

import yaml
from llm_gateway import Gateway
from loguru import logger

from revision.config import PATHS, registry
from revision.generate import Generator
from revision.ingest import Chunk, chunk_markdown, convert_file
from revision.schemas import CourseContent
from revision.store import VectorIndex


def slugify(text: str) -> str:
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60] or "cours"


def ingest_course(slug: str, content_dir: Path | None = None) -> tuple[str, list[Chunk]]:
    """Convertit les fichiers d'un cours du registre et enregistre source.md + chunks.json."""
    course = registry()["courses"][slug]
    content_dir = content_dir or PATHS.content
    texts = [convert_file(PATHS.cours / f) for f in course["files"] if (PATHS.cours / f).exists()]
    markdown = f"# {course['title']}\n\n" + "\n\n".join(texts)
    return markdown, save_source(slug, markdown, content_dir)


def save_source(slug: str, markdown: str, content_dir: Path) -> list[Chunk]:
    out = content_dir / slug
    out.mkdir(parents=True, exist_ok=True)
    (out / "source.md").write_text(markdown, encoding="utf-8")
    chunks = chunk_markdown(slug, markdown)
    (out / "chunks.json").write_text(
        json.dumps([asdict(c) for c in chunks], ensure_ascii=False), encoding="utf-8"
    )
    return chunks


def load_chunks(slug: str, content_dir: Path | None = None) -> list[Chunk]:
    path = (content_dir or PATHS.content) / slug / "chunks.json"
    return (
        [Chunk(**c) for c in json.loads(path.read_text(encoding="utf-8"))] if path.exists() else []
    )


def add_course(
    path_or_text: Path | str,
    title: str | None,
    theme: str,
    gateway: Gateway,
    content_dir: Path | None = None,
    filename: str | None = None,
) -> CourseContent:
    """Ajoute un NOUVEAU cours (fichier, texte déjà converti) : ingestion, index, génération, registre."""
    content_dir = content_dir or PATHS.content
    if isinstance(path_or_text, Path):
        markdown = convert_file(path_or_text)
        title = title or path_or_text.stem
    else:
        markdown = path_or_text
        title = title or (filename or "Nouveau cours")
    slug = slugify(title)
    markdown = f"# {title}\n\n{markdown}" if not markdown.lstrip().startswith("# ") else markdown
    chunks = save_source(slug, markdown, content_dir)
    index_path = content_dir / "_index.json"
    index = VectorIndex.load(index_path)
    index.add(chunks, gateway)
    index.save(index_path)
    content = Generator(gateway, content_dir).generate(slug, title, theme, markdown, chunks)
    register_extra(slug, title, theme, content_dir)
    return content


def register_extra(slug: str, title: str, theme: str, content_dir: Path) -> None:
    """Cours ajoutés après coup : listés dans content/_extra.yaml (le registre principal reste intact)."""
    path = content_dir / "_extra.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    data = data or {}
    data[slug] = {"title": title, "theme": theme}
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=True), encoding="utf-8")


def all_courses(content_dir: Path | None = None) -> dict[str, dict]:
    content_dir = content_dir or PATHS.content
    courses = {
        k: {"title": v["title"], "theme": v["theme"]} for k, v in registry()["courses"].items()
    }
    extra = content_dir / "_extra.yaml"
    if extra.exists():
        courses.update(yaml.safe_load(extra.read_text(encoding="utf-8")) or {})
    return courses


def build_index(gateway: Gateway, content_dir: Path | None = None) -> int:
    content_dir = content_dir or PATHS.content
    index = VectorIndex()
    n = 0
    for slug in all_courses(content_dir):
        chunks = load_chunks(slug, content_dir)
        if chunks:
            index.add(chunks, gateway)
            n += len(chunks)
    index.save(content_dir / "_index.json")
    logger.info("Index : {} passages", n)
    return n
