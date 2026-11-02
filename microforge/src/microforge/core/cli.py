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


def sketch_dir(project: Path) -> Path:
    """Dossier du sketch principal : celui dont le .ino porte le nom du dossier (exigence Arduino).

    Le dossier ``wokwi/`` contient aussi un ``sketch.ino`` : il ne doit pas être choisi.
    """
    for ino in sorted(project.glob("*/*.ino")):
        if ino.stem == ino.parent.name:
            return ino.parent
    raise FileNotFoundError(f"Aucun sketch principal dans {project}")


def _board_for_fqbn(fqbn: str):
    cat = get_catalog()
    board = next((b for b in cat.boards.values() if b.fqbn == fqbn), None)
    if board is None:
        raise typer.BadParameter(f"Aucune carte du catalogue avec le FQBN {fqbn}")
    return cat, board


def templates_for_board(cat, board, only_demo: bool = False) -> list[str]:
    """Modèles compatibles avec la famille de la carte (Wi-Fi exigé -> carte Wi-Fi)."""
    ids = DEMO_TEMPLATES if only_demo else sorted(cat.templates)
    return [
        tid
        for tid in ids
        if board.family in cat.templates[tid].board_families
        and (board.wifi or not cat.templates[tid].requires_wifi)
    ]


@app.command("libs")
def libs(fqbn: str = typer.Option("arduino:avr:uno")) -> None:
    """Bibliothèques Arduino nécessaires à tous les modèles compatibles (une par ligne, pour la CI)."""
    cat, board = _board_for_fqbn(fqbn)
    b = ProjectBuilder(cat)
    needed: set[str] = set()
    for tid in templates_for_board(cat, board):
        needed |= set(b.build(b.spec_from_template(tid, board.id)).libraries)
    for name in sorted(needed):
        typer.echo(name)


@app.command("compile-demo")
def compile_demo(
    fqbn: str = typer.Option("arduino:avr:uno"),
    out: Path = typer.Option(Path("build/demo")),
    all_templates: bool = typer.Option(
        True, "--all/--demo", help="Tous les modèles ou seulement la démo"
    ),
) -> None:
    """Génère les projets et les compile VRAIMENT avec arduino-cli (job « firmware » de la CI)."""
    cat, board = _board_for_fqbn(fqbn)
    cli = shutil.which("arduino-cli")
    if cli is None:
        raise typer.Exit("arduino-cli introuvable")
    b = ProjectBuilder(cat)
    failures: list[str] = []
    targets = templates_for_board(cat, board, only_demo=not all_templates)
    for tid in targets:
        result = b.build(b.spec_from_template(tid, board.id))
        write_project(b, result, out / tid)
        sketch = sketch_dir(out / tid)
        proc = subprocess.run(  # noqa: S603 — arguments contrôlés (FQBN du catalogue)
            [cli, "compile", "--fqbn", fqbn, str(sketch)], capture_output=True, text=True
        )
        status = "OK" if proc.returncode == 0 else "ÉCHEC"
        size = next(
            (
                ln
                for ln in proc.stdout.splitlines()
                if "Sketch uses" in ln or "Le croquis utilise" in ln
            ),
            "",
        )
        typer.echo(f"{status:5s} {tid:28s} {size}")
        if proc.returncode != 0:
            failures.append(tid)
            typer.echo(proc.stdout[-2000:] + proc.stderr[-2000:])
    typer.echo(f"\n{len(targets) - len(failures)}/{len(targets)} projets compilés pour {fqbn}")
    if failures:
        typer.echo("Échecs : " + ", ".join(failures))
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
