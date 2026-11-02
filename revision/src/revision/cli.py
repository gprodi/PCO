"""CLI ``revise`` : ingest | seed | generate | index | add | export | serve | podcast | status."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from revision.config import PATHS, registry

app = typer.Typer(
    help="Révisions DevIA — cours -> fiches, QCM, flashcards, exercices, cartes mentales, podcasts.",
    no_args_is_help=True,
)


def _gateway():
    from llm_gateway import Gateway

    return Gateway.from_env()


@app.command()
def ingest(slug: str = typer.Argument(None, help="un cours ; tous par défaut")) -> None:
    """Convertit les supports de cours/ en Markdown + passages."""
    from revision.pipeline import ingest_course

    for s in [slug] if slug else registry()["courses"]:
        md, chunks = ingest_course(s)
        typer.echo(f"{s:26s} {len(md):7d} caractères, {len(chunks):4d} passages")


@app.command()
def seed() -> None:
    """Installe le contenu initial rédigé à la main (revision/seed/*.yaml)."""
    from revision.seed import apply_seeds

    typer.echo(f"{len(apply_seeds())} cours installés")


@app.command()
def generate(slug: str = typer.Argument(None), force: bool = False) -> None:
    """Génère les livrables avec le LLM (local d'abord) pour un cours ou tous ceux sans contenu."""
    from revision.generate import Generator
    from revision.pipeline import ingest_course

    gen = Generator(_gateway())
    for s in [slug] if slug else registry()["courses"]:
        if not slug and (PATHS.content / s / "content.json").exists() and not force:
            continue
        md, chunks = ingest_course(s)
        c = registry()["courses"][s]
        gen.generate(s, c["title"], c["theme"], md, chunks, force=force)
        typer.echo(f"{s} : généré")


@app.command()
def index() -> None:
    """Construit l'index sémantique (embeddings) pour le chat."""
    from revision.pipeline import build_index

    typer.echo(f"{build_index(_gateway())} passages indexés")


@app.command()
def add(source: str, title: str = typer.Option(None), theme: str = typer.Option("bases")) -> None:
    """Ajoute un nouveau cours : fichier (md, pdf, pptx, html, docx, ipynb, txt) ou URL."""
    from revision.ingest import convert_url
    from revision.pipeline import add_course
    from revision.site_export import export

    target: Path | str = Path(source) if Path(source).exists() else convert_url(source)
    content = add_course(target, title, theme, _gateway())
    export()
    typer.echo(f"Ajouté : {content.slug} ({content.titre})")


@app.command("export")
def export_cmd() -> None:
    """Exporte le contenu vers le site Astro."""
    from revision.site_export import export

    typer.echo(json.dumps(export(), ensure_ascii=False))


@app.command()
def serve(port: int = 8765) -> None:
    """API locale (ajout de cours, chat, oral blanc)."""
    import uvicorn

    uvicorn.run("revision.api:app", host="127.0.0.1", port=port)


@app.command()
def podcast(
    slug: str,
    voice_a: str = "fr_FR-siwis-medium",
    voice_b: str = "fr_FR-upmc-medium",
    models: Path = Path("models/piper"),
) -> None:
    """Génère l'audio du podcast d'un cours (Piper, local)."""
    from revision.podcast import synthesize
    from revision.schemas import CourseContent

    content = CourseContent.model_validate_json((PATHS.content / slug / "content.json").read_text())
    out = synthesize(
        content.podcast, PATHS.content / slug / "podcast.mp3", voice_a, voice_b, models
    )
    typer.echo(f"Audio : {out}")


@app.command()
def status() -> None:
    """État : cours, contenus disponibles, index."""
    from revision.pipeline import all_courses

    for slug, info in all_courses().items():
        has = (PATHS.content / slug / "content.json").exists()
        typer.echo(f"{'✅' if has else '⬜'} {slug:26s} {info['title']}")


if __name__ == "__main__":
    app()
