"""Génération des livrables de révision par LLM (local d'abord) avec cache et vérification.

* Cache : empreinte SHA-256 (texte du cours + version des prompts) -> pas de régénération inutile.
* Ancrage : le LLM reçoit des passages numérotés et doit citer leurs identifiants ; un vérificateur
  rejette les éléments dont les sources n'existent pas (limite les hallucinations).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from llm_gateway import Gateway
from loguru import logger
from pydantic import BaseModel

from revision.config import PATHS, referentiel
from revision.ingest.chunker import Chunk
from revision.schemas import CourseContent, Exercices, Fiche, Flashcards, MindMap, Podcast, Quiz

PROMPT_VERSION = "2026-11-v1"

SYSTEM = (
    "Tu es un formateur expert du titre « Développeur en intelligence artificielle » (Simplon). "
    "Tu produis des supports de révision exacts, en français, à partir UNIQUEMENT des passages fournis. "
    "N'invente aucune commande, API ou chiffre absent des passages. Code : extraits courts et corrects."
)

TASKS: dict[str, tuple[type[BaseModel], str]] = {
    "fiche": (
        Fiche,
        "Rédige une fiche de révision : résumé, objectifs, 5 à 10 notions (terme/définition), points clés, 1 à 3 extraits de code commentés, pièges fréquents, compétences C1–C21 concernées, et la liste des identifiants de passages utilisés dans 'sources'.",
    ),
    "quiz": (
        Quiz,
        "Écris 8 questions de QCM (4 choix, une seule bonne réponse, explication courte citant le cours, difficulté 1 à 3).",
    ),
    "flashcards": (
        Flashcards,
        "Écris 12 flashcards (recto : question ou terme ; verso : réponse en une ou deux phrases).",
    ),
    "exercices": (
        Exercices,
        "Propose 3 exercices progressifs (niveaux 1, 2, 3) avec énoncé, 1 à 3 indices et un corrigé complet (code si pertinent).",
    ),
    "mindmap": (
        MindMap,
        "Construis une carte mentale en liste Markdown hiérarchique (titre # = nom du cours, 4 à 7 branches, 2 à 4 niveaux).",
    ),
    "podcast": (
        Podcast,
        "Écris le script d'un podcast de 3 minutes à deux voix : A (animatrice curieuse) et B (expert). 12 à 18 répliques, ton vivant, sans lire le code.",
    ),
}


def content_hash(markdown: str) -> str:
    return hashlib.sha256((PROMPT_VERSION + markdown).encode()).hexdigest()


def competences_prompt() -> str:
    return "\n".join(f"{c['id']} : {c['titre']}" for c in referentiel()["competences"])


def passages_prompt(chunks: list[Chunk], limit_chars: int = 24000) -> str:
    out, size = [], 0
    for c in chunks:
        block = f"[{c.id}] ({c.heading})\n{c.text}\n"
        if size + len(block) > limit_chars:
            break
        out.append(block)
        size += len(block)
    return "\n".join(out)


def verify_sources(fiche: Fiche, chunks: list[Chunk]) -> Fiche:
    valid = {c.id for c in chunks}
    kept = [s for s in fiche.sources if s in valid]
    if fiche.sources and not kept:
        logger.warning("Aucune source citée n'existe : fiche marquée « à vérifier »")
        fiche.points_cles.insert(0, "⚠️ Fiche générée sans source vérifiable : à relire.")
    fiche.sources = kept
    return fiche


class Generator:
    def __init__(self, gateway: Gateway, content_dir: Path | None = None) -> None:
        self.gateway = gateway
        self.content_dir = content_dir or PATHS.content

    def generate(
        self,
        slug: str,
        title: str,
        theme: str,
        markdown: str,
        chunks: list[Chunk],
        force: bool = False,
    ) -> CourseContent:
        out_dir = self.content_dir / slug
        meta_path = out_dir / "meta.json"
        digest = content_hash(markdown)
        if not force and meta_path.exists() and (out_dir / "content.json").exists():
            meta = json.loads(meta_path.read_text())
            if meta.get("hash") == digest:
                logger.info("{} : inchangé (cache)", slug)
                return CourseContent.model_validate_json((out_dir / "content.json").read_text())
        context = f"Cours : {title}\nCompétences du référentiel :\n{competences_prompt()}\n\nPassages :\n{passages_prompt(chunks)}"
        parts = {}
        for name, (schema, instruction) in TASKS.items():
            logger.info("{} : génération {}", slug, name)
            parts[name] = self.gateway.structured(
                f"{context}\n\nTâche : {instruction}",
                schema=schema,
                system=SYSTEM,
                role="text",
                max_tokens=6000,
            )
        parts["fiche"] = verify_sources(parts["fiche"], chunks)
        content = CourseContent(slug=slug, titre=title, theme=theme, origine="llm", **parts)
        save_content(content, out_dir, digest)
        return content


def save_content(content: CourseContent, out_dir: Path, digest: str = "") -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "content.json").write_text(content.model_dump_json(indent=2), encoding="utf-8")
    (out_dir / "meta.json").write_text(
        json.dumps(
            {"hash": digest, "prompt_version": PROMPT_VERSION, "origine": content.origine}, indent=2
        ),
        encoding="utf-8",
    )
