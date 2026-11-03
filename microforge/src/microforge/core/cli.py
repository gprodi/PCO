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
    return [tid for tid in ids if cat.template_fits(tid, board)]


@app.command("ci-matrix")
def ci_matrix() -> None:
    """Matrice JSON de la CI.

    Une entrée par famille (carte de référence : tous les projets + croquis de fumée de chaque
    carte de la famille), plus une entrée par variante de puce marquée ``ci_compile_all``
    (ESP32-S3, C3, C6, RP2350 : tous les projets).
    """
    cat = get_catalog()
    include = []
    for fam in cat.families.values():
        rep = cat.representative(fam.id)
        boards = [rep] + [b for b in cat.boards.values() if b.family == fam.id and b.ci_compile_all]
        for board in boards:
            include.append(
                {
                    "name": f"{fam.label.split(' (')[0]} — {board.name.split(' (')[0]}",
                    "family": fam.id,
                    "fqbn": board.fqbn,
                    "core": fam.core,
                    "index": fam.index_url,
                    "smoke": board is rep,
                }
            )
    typer.echo(json.dumps({"include": include}, ensure_ascii=False))


@app.command("board-smoke")
def board_smoke(
    family: str = typer.Option(..., help="Famille dont toutes les cartes sont vérifiées"),
    out: Path = typer.Option(Path("build/smoke")),
) -> None:
    """Compile un croquis minimal (LED, I2C, SPI) pour CHAQUE carte d'une famille : FQBN et broches valides."""
    cat = get_catalog()
    cli = shutil.which("arduino-cli")
    if cli is None:
        raise typer.Exit("arduino-cli introuvable")
    failures = []
    seen: set[str] = set()
    for board in (b for b in cat.boards.values() if b.family == family):
        if board.fqbn in seen:  # ex. DevKit V1 et WROVER : même FQBN, une compilation suffit
            continue
        seen.add(board.fqbn)
        free = [
            p for p in board.pins if "digital" in p.caps and not p.reserved and not p.input_only
        ]
        pin = free[0].label if board.code_labels == "all" else str(free[0].gpio)
        sketch = out / board.id.replace("-", "_")
        sketch.mkdir(parents=True, exist_ok=True)
        (sketch / f"{sketch.name}.ino").write_text(
            "#include <Wire.h>\n#include <SPI.h>\n"
            f"// Croquis de fumée MicroForge pour {board.name}\n"
            f"void setup() {{ pinMode({pin}, OUTPUT); Wire.begin(); SPI.begin(); }}\n"
            f"void loop() {{ digitalWrite({pin}, HIGH); delay(500); digitalWrite({pin}, LOW); delay(500); }}\n",
            encoding="utf-8",
        )
        proc = subprocess.run(  # noqa: S603 — FQBN issus du catalogue
            [cli, "compile", "--fqbn", board.fqbn, str(sketch)], capture_output=True, text=True
        )
        typer.echo(f"{'OK' if proc.returncode == 0 else 'ÉCHEC':5s} {board.id:28s} {board.fqbn}")
        if proc.returncode != 0:
            failures.append(board.id)
            typer.echo(proc.stdout[-1500:] + proc.stderr[-1500:])
    if failures:
        raise typer.Exit(code=1)


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
    skipped: list[str] = []
    for tid in targets:
        result = b.build(b.spec_from_template(tid, board.id))
        errors = [i for i in result.issues if i.severity.value == "error"]
        if errors and {i.code for i in errors} <= {"NO_PIN", "NO_I2C_BUS", "NO_SPI_BUS", "CODEGEN"}:
            skipped.append(tid)
            typer.echo(f"—     {tid:28s} non réalisable sur cette carte : {errors[0].message}")
            continue
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
    done = len(targets) - len(skipped)
    typer.echo(
        f"\n{done - len(failures)}/{done} projets compilés pour {fqbn}"
        + (f" ({len(skipped)} non réalisables faute de broches)" if skipped else "")
    )
    if failures:
        typer.echo("Échecs : " + ", ".join(failures))
        raise typer.Exit(code=1)


@app.command("verify-boards")
def verify_boards(
    out: Path = typer.Option(None, help="écrire le rapport JSON dans ce fichier"),
) -> None:
    """Compare les bus I2C/SPI des cartes avec les variantes officielles des cœurs (réseau)."""
    from microforge.core.verify_boards import BoardVerifier, report

    result = report(BoardVerifier().run())
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if out:
        out.write_text(text, encoding="utf-8")
    typer.echo(text)
    if result["ecarts"]:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
