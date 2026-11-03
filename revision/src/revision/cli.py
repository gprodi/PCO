"""CLI ``revise`` : start | ingest | seed | generate | index | add | export | serve | podcast | status."""

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
def index(
    vector_url: str = typer.Option(
        None,
        "--vector-url",
        envvar="REVISION_VECTOR_URL",
        help="postgresql+psycopg://… : index dans PostgreSQL + pgvector (sinon JSON local)",
    ),
) -> None:
    """Construit l'index sémantique (embeddings) pour le chat."""
    from revision.pipeline import build_index

    where = "PostgreSQL + pgvector" if (vector_url or "").startswith("postgresql") else "JSON local"
    typer.echo(f"{build_index(_gateway(), url=vector_url or '')} passages indexés ({where})")


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


SITE_URL = "http://localhost:4321/PCO/"


def _ollama_hint() -> str:
    """Une ligne d'état sur l'IA locale (le site fonctionne sans, le chat non)."""
    import httpx
    from llm_gateway.config import GatewaySettings

    url = GatewaySettings().ollama_base_url
    try:
        models = [m["name"] for m in httpx.get(f"{url}/api/tags", timeout=1.5).json()["models"]]
    except (httpx.HTTPError, KeyError, ValueError):
        return (
            "IA locale : Ollama introuvable. Le site, les QCM et les flashcards marchent ; "
            "pour le chat et l'ajout de cours, installer https://ollama.com puis « ollama pull qwen3:4b »."
        )
    if not models:
        return "IA locale : Ollama tourne mais n'a aucun modèle : « ollama pull qwen3:4b »."
    return f"IA locale : Ollama prêt ({', '.join(models[:4])})."


@app.command()
def start(
    port: int = 8765,
    open_browser: bool = typer.Option(True, "--open/--no-open", help="ouvrir le navigateur"),
) -> None:
    """Lance TOUT l'outil de révision : API locale + site (http://localhost:4321/PCO/)."""
    import shutil
    import subprocess
    import threading
    import webbrowser

    import uvicorn

    npm = shutil.which("npm")
    if npm is None:
        typer.echo(
            "Node.js est requis pour le site : https://nodejs.org (version 22 ou plus).", err=True
        )
        raise typer.Exit(1)
    site = PATHS.revision / "site"
    if not (site / "node_modules").exists():
        typer.echo("Première utilisation : installation des dépendances du site (npm install)…")
        subprocess.run([npm, "install"], cwd=site, check=True)  # noqa: S603 — npm trouvé par which
    typer.echo(_ollama_hint())
    proc = subprocess.Popen([npm, "run", "dev"], cwd=site, **_new_group())  # noqa: S603
    typer.echo(f"Site : {SITE_URL}   API : http://127.0.0.1:{port}   (Ctrl+C pour tout arrêter)")
    if open_browser:
        threading.Timer(5.0, webbrowser.open, [SITE_URL]).start()
    try:
        uvicorn.run("revision.api:app", host="127.0.0.1", port=port)
    finally:
        _stop_tree(proc)


def _new_group() -> dict:
    """npm lance « sh -c astro dev » puis node : on les met dans un groupe pour tout arrêter d'un coup."""
    import subprocess
    import sys

    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _stop_tree(proc) -> None:
    """Arrête npm ET ses descendants (sinon le serveur du site survit à Ctrl+C)."""
    import contextlib
    import os
    import signal
    import subprocess
    import sys
    import time

    if sys.platform == "win32":
        if proc.poll() is not None:
            return
        subprocess.run(  # noqa: S603 — outil système Windows, PID entier
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)],  # noqa: S607
            capture_output=True,
            check=False,
        )
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    # Le serveur du site s'arrête proprement en quelques secondes ; au-delà de 10 s, arrêt forcé.
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        proc.poll()
        try:
            os.killpg(proc.pid, 0)  # reste-t-il un membre du groupe ?
        except ProcessLookupError:
            return
        time.sleep(0.2)
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGKILL)
    proc.wait()


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
    from revision.store import open_course_index

    for slug, info in all_courses().items():
        has = (PATHS.content / slug / "content.json").exists()
        typer.echo(f"{'✅' if has else '⬜'} {slug:26s} {info['title']}")
    try:
        idx = open_course_index(PATHS.content)
        typer.echo(f"Index ({idx.backend}) : {len(idx)} passages")
    except Exception as exc:  # base injoignable : l'état des cours reste affiché
        typer.echo(f"Index : indisponible ({exc.__class__.__name__})")


if __name__ == "__main__":
    app()
