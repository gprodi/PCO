"""Exporte le contenu vers le site Astro (``revision/site/src/data``) : cours, référentiel, boilerplates."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from revision.config import PATHS, referentiel, registry
from revision.pipeline import all_courses


def _boilerplates(root: Path) -> list[dict]:
    out = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()) if root.exists() else []:
        meta_path = d / "copier.yml"
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        files = sorted(
            str(p.relative_to(d)) for p in d.rglob("*") if p.is_file() and p.name != "copier.yml"
        )
        out.append(
            {
                "id": d.name,
                "titre": meta.get("_titre", d.name),
                "description": meta.get("_description", ""),
                "cours": meta.get("_cours", []),
                "competences": meta.get("_competences", []),
                "fichiers": files,
                "apercu": {
                    f: (d / f).read_text(encoding="utf-8", errors="replace")[:4000]
                    for f in files[:12]
                },
            }
        )
    return out


MF_DATA = PATHS.root / "microforge" / "src" / "microforge" / "core" / "data"


def _ideas() -> list[dict]:
    """Idées de projets MicroForge par thème (lues directement depuis les YAML du catalogue)."""
    path = MF_DATA / "idees.yaml"
    if not path.exists():
        return []
    names: dict[str, str] = {}
    for comp_file in sorted((MF_DATA / "components").glob("*.yaml")):
        for comp in yaml.safe_load(comp_file.read_text(encoding="utf-8")):
            names[comp["id"]] = comp["name"]
    themes = yaml.safe_load(path.read_text(encoding="utf-8"))["themes"]
    for theme in themes:
        for idea in theme["idees"]:
            idea["composants_noms"] = [names.get(c, c) for c in idea["composants"]]
    return themes


def export(site_data: Path | None = None, content_dir: Path | None = None) -> dict[str, int]:
    site_data = site_data or PATHS.site_data
    content_dir = content_dir or PATHS.content
    (site_data / "content").mkdir(parents=True, exist_ok=True)
    courses = []
    for slug, info in all_courses(content_dir).items():
        path = content_dir / slug / "content.json"
        has = path.exists()
        if has:
            shutil.copy(path, site_data / "content" / f"{slug}.json")
        audio = content_dir / slug / "podcast.mp3"
        if audio.exists():
            target = PATHS.revision / "site" / "public" / "podcasts"
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy(audio, target / f"{slug}.mp3")
        courses.append(
            {
                "slug": slug,
                "titre": info["title"],
                "theme": info["theme"],
                "disponible": has,
                "audio": audio.exists(),
            }
        )
    themes = registry()["themes"]
    (site_data / "courses.json").write_text(
        json.dumps({"themes": themes, "courses": courses}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    ref = referentiel()
    (site_data / "referentiel.json").write_text(
        json.dumps(ref, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    bps = _boilerplates(PATHS.boilerplates)
    (site_data / "boilerplates.json").write_text(
        json.dumps(bps, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    ideas = _ideas()
    (site_data / "idees.json").write_text(
        json.dumps(ideas, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return {
        "courses": len(courses),
        "with_content": sum(c["disponible"] for c in courses),
        "boilerplates": len(bps),
        "idees": sum(len(t["idees"]) for t in ideas),
    }
