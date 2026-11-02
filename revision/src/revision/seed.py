"""Contenu initial rédigé à la main (``revision/seed/<slug>.yaml``) -> ``content/<slug>/content.json``.

Permet d'avoir un site complet tout de suite ; les cours ajoutés ensuite sont générés par le LLM local.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from revision.config import PATHS, registry
from revision.generate import save_content
from revision.schemas import CourseContent


def load_seed(path: Path) -> CourseContent:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    slug = path.stem
    course = registry()["courses"].get(slug, {})
    return CourseContent(
        slug=slug,
        titre=raw.get("titre") or course.get("title", slug),
        theme=raw.get("theme") or course.get("theme", "bases"),
        fiche=raw["fiche"],
        quiz={"questions": raw["qcm"]},
        flashcards={"cartes": raw["flashcards"]},
        exercices={"exercices": raw["exercices"]},
        mindmap={"markdown": raw["mindmap"]},
        podcast={
            "titre": raw.get("podcast_titre", f"Révision : {course.get('title', slug)}"),
            "repliques": raw["podcast"],
        },
        origine="seed",
    )


def apply_seeds(seed_dir: Path | None = None, content_dir: Path | None = None) -> list[str]:
    seed_dir = seed_dir or PATHS.seed
    content_dir = content_dir or PATHS.content
    done = []
    for path in sorted(seed_dir.glob("*.yaml")):
        content = load_seed(path)
        save_content(content, content_dir / content.slug, digest="seed")
        done.append(content.slug)
    return done
