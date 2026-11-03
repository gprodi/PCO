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
from revision.store import open_course_index


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


def content_chunks(content: CourseContent) -> list[Chunk]:
    """Passages issus de la fiche rédigée (notions, points clés, pièges, exercices corrigés…).

    Le RAG s'appuie ainsi sur le contenu relu à la main, pas seulement sur le texte brut des supports.
    """
    slug, f = content.slug, content.fiche
    out: list[Chunk] = []

    def add(key: str, heading: str, text: str) -> None:
        if text.strip():
            out.append(Chunk(f"{slug}#{key}", slug, f"{content.titre} — {heading}", text.strip()))

    add("resume", "Résumé", f.resume + "\n" + "\n".join(f"- {o}" for o in f.objectifs))
    for i, n in enumerate(f.notions):
        add(f"notion-{i}", f"Notion : {n.terme}", n.definition)
    add("points-cles", "Points clés", "\n".join(f"- {p}" for p in f.points_cles))
    for i, c in enumerate(f.code):
        add(f"code-{i}", f"Code : {c.titre}", f"{c.explication}\n```{c.lang}\n{c.code}\n```")
    add("pieges", "Pièges", "\n".join(f"- {p}" for p in f.pieges))
    for i, a in enumerate(f.aller_plus_loin):
        add(f"plus-{i}", f"Aller plus loin : {a.titre}", f"{a.contenu} {a.lien}".strip())
    add("jury", "Référentiel et jury", f.jury)
    for i, e in enumerate(content.exercices.exercices):
        add(f"exo-{i}", f"Exercice : {e.titre}", f"{e.enonce}\n\nCorrigé :\n{e.corrige}")
    qs = content.quiz.questions
    for start in range(0, len(qs), 4):
        add(
            f"qcm-{start // 4}",
            "QCM corrigé",
            "\n\n".join(
                f"Q : {q.question}\nR : {q.choix[q.bonne]}. {q.explication}".strip()
                for q in qs[start : start + 4]
            ),
        )
    cards = content.flashcards.cartes
    for start in range(0, len(cards), 6):
        add(
            f"cartes-{start // 6}",
            "Flashcards",
            "\n".join(f"- {c.recto} → {c.verso}" for c in cards[start : start + 6]),
        )
    return out


def load_content(slug: str, content_dir: Path | None = None) -> CourseContent | None:
    path = (content_dir or PATHS.content) / slug / "content.json"
    return (
        CourseContent.model_validate_json(path.read_text(encoding="utf-8"))
        if path.exists()
        else None
    )


def course_passages(slug: str, content_dir: Path | None = None) -> list[Chunk]:
    """Tout ce qui est indexé pour un cours : texte des supports + fiche rédigée."""
    content = load_content(slug, content_dir)
    return load_chunks(slug, content_dir) + (content_chunks(content) if content else [])


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
    index = open_course_index(content_dir)
    index.add(chunks, gateway)  # d'abord le texte brut (chat disponible pendant la génération)
    content = Generator(gateway, content_dir).generate(slug, title, theme, markdown, chunks)
    index.add(chunks + content_chunks(content), gateway)
    index.save()
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


def build_index(gateway: Gateway, content_dir: Path | None = None, url: str | None = None) -> int:
    """Reconstruit tout l'index (JSON local, ou pgvector si ``url``/``REVISION_VECTOR_URL``)."""
    content_dir = content_dir or PATHS.content
    index = open_course_index(content_dir, url)
    index.clear()
    n = 0
    for slug in all_courses(content_dir):
        chunks = course_passages(slug, content_dir)
        if chunks:
            index.add(chunks, gateway)
            n += len(chunks)
    index.save(content_dir / "_index.json")
    logger.info("Index ({}) : {} passages", index.backend, n)
    return n
