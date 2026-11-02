"""CLI MicroForge : ``microforge catalog | suggest | build | goal | compile-demo``."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import typer

from microforge.core.builder import ProjectBuilder
from microforge.core.catalog import get_catalog
from microforge.core.suggest import suggest_projects

app = typer.Typer(
    help="MicroForge : du stock électronique au montage programmé.", no_args_is_help=True
)

DEMO_TEMPLATES = [
    "station-meteo-oled",
    "radar-de-recul",
    "barriere-servo",
    "veilleuse-auto",
    "feu-tricolore-pieton",
]


def parse_stock(text: str) -> dict[str, int]:
    """« esp32=1, dht22=2 » -> {"esp32": 1, "dht22": 2} (quantité 1 par défaut)."""
    stock: dict[str, int] = {}
    for item in filter(None, (s.strip() for s in text.split(","))):
        name, _, qty = item.partition("=")
        stock[name.strip()] = int(qty) if qty.strip() else 1
    return stock


def write_project(builder: ProjectBuilder, result, out: Path, as_zip: bool = False) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    if as_zip:
        path = out / f"{result.spec.template_id or 'projet'}.zip"
        path.write_bytes(builder.bundle(result))
        return path
    for rel, content in builder.files(result).items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return out


@app.command()
def catalog(category: str = typer.Option("", help="filtrer par catégorie")) -> None:
    """Liste les cartes, composants et modèles de projets."""
    cat = get_catalog()
    typer.echo("Cartes :")
    for b in cat.boards.values():
        typer.echo(f"  {b.id:18s} {b.name}")
    typer.echo("Composants :")
    for c in cat.components.values():
        if not category or c.category == category:
            typer.echo(f"  {c.id:26s} [{c.category}] {c.name}")
    typer.echo(f"Modèles de projets : {len(cat.templates)}")


@app.command()
def suggest(
    stock: str = typer.Option(..., help="ex. 'esp32-devkit-v1=1,dht22=1,oled=1'"), limit: int = 10
) -> None:
    """Projets réalisables avec un stock."""
    for s in suggest_projects(parse_stock(stock), limit=limit):
        d = s.to_dict()
        flag = "✅" if d["feasible_now"] else f"🛒 manque {d['missing']}"
        typer.echo(f"{d['score']:6.1f}  {d['title']:40s} sur {d['board']:16s} {flag}")


@app.command()
def build(
    template: str,
    board: str = typer.Option("arduino-uno"),
    out: Path = typer.Option(Path("build")),
    zip_: bool = typer.Option(False, "--zip"),
) -> None:
    """Génère un projet complet à partir d'un modèle du catalogue."""
    b = ProjectBuilder()
    result = b.build(b.spec_from_template(template, board))
    path = write_project(b, result, out / template, zip_)
    for issue in result.issues:
        typer.echo(f"[{issue.severity.value}] {issue.code} — {issue.message}")
    typer.echo(f"Projet écrit dans {path}")


@app.command()
def goal(
    text: str,
    board: str = typer.Option(None),
    stock: str = typer.Option("", help="stock à privilégier"),
    out: Path = typer.Option(Path("build")),
) -> None:
    """« Je veux construire… » (utilise le LLM via llm_gateway, local d'abord)."""
    from llm_gateway import Gateway

    from microforge.core.generator import ProjectGenerator

    gen = ProjectGenerator(Gateway.from_env())
    spec = gen.from_goal(text, parse_stock(stock) if stock else None, board)
    b = ProjectBuilder()
    result = b.build(spec)
    path = write_project(b, result, out / "goal")
    typer.echo(
        json.dumps({"title": spec.title, "board": spec.board, "ok": result.ok}, ensure_ascii=False)
    )
    typer.echo(f"Projet écrit dans {path}")


@app.command("compile-demo")
def compile_demo(
    fqbn: str = typer.Option("arduino:avr:uno"),
    out: Path = typer.Option(Path("build/demo")),
) -> None:
    """Génère les projets de démonstration et les compile avec arduino-cli (CI)."""
    cat = get_catalog()
    board = next((b for b in cat.boards.values() if b.fqbn == fqbn), None)
    if board is None:
        raise typer.BadParameter(f"Aucune carte du catalogue avec le FQBN {fqbn}")
    cli = shutil.which("arduino-cli")
    if cli is None:
        raise typer.Exit("arduino-cli introuvable")
    b = ProjectBuilder(cat)
    failures = 0
    for tid in DEMO_TEMPLATES:
        result = b.build(b.spec_from_template(tid, board.id))
        write_project(b, result, out / tid)
        sketch = next((out / tid).glob("*/*.ino")).parent
        proc = subprocess.run(  # noqa: S603 — arguments contrôlés (FQBN du catalogue)
            [cli, "compile", "--fqbn", fqbn, str(sketch)], capture_output=True, text=True
        )
        status = "OK" if proc.returncode == 0 else "ÉCHEC"
        typer.echo(f"{status:5s} {tid}")
        if proc.returncode != 0:
            failures += 1
            typer.echo(proc.stdout[-2000:] + proc.stderr[-2000:])
    if failures:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
