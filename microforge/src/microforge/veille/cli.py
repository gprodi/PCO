"""CLI ``mf-veille`` : collecte des flux de l'OPML -> brouillon de synthèse classé par thématique."""

from __future__ import annotations

import json
from pathlib import Path

import typer

app = typer.Typer(help="Veille technologique MicroForge (E2).", no_args_is_help=True)
DEFAULT_OPML = Path(__file__).resolve().parents[3] / "veille" / "sources.opml"


@app.command()
def collect(
    opml: Path = typer.Option(DEFAULT_OPML, help="fichier OPML des sources"),
    days: int = typer.Option(7, help="fenêtre en jours"),
    per_theme: int = typer.Option(5, help="articles retenus par thématique"),
    out: Path = typer.Option(Path("veille-sortie"), help="dossier de sortie"),
    llm: bool = typer.Option(
        False, "--llm/--no-llm", help="résumé « En bref » par le modèle local"
    ),
) -> None:
    """Lit les flux, garde les articles récents et pertinents, écrit brouillon.md + articles.json."""
    from microforge.veille.rank import select
    from microforge.veille.report import draft
    from microforge.veille.sources import fetch, read_opml

    feeds = read_opml(opml)
    results = fetch(feeds)
    items = [it for r in results for it in r.items]
    selection = select(items, days=days, per_theme=per_theme)
    summary = None
    if llm:
        summary = _summarize(selection)
    out.mkdir(parents=True, exist_ok=True)
    (out / "brouillon.md").write_text(draft(selection, results, summary), encoding="utf-8")
    payload = {
        "flux": [
            {"titre": r.feed.title, "url": r.feed.url, "statut": r.status, "articles": len(r.items),
             "erreur": r.error}
            for r in results
        ],
        "selection": {t: [it.to_dict() for it in its] for t, its in selection.items()},
    }  # fmt: skip
    (out / "articles.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
    ok = sum(r.status == "ok" for r in results)
    retained = sum(len(v) for v in selection.values())
    typer.echo(f"{ok}/{len(results)} flux lus, {len(items)} articles, {retained} retenus -> {out}")


def _summarize(selection: dict) -> str | None:
    """« En bref » par la passerelle (Ollama puis Gemini gratuit) ; rien si aucun modèle."""
    from llm_gateway import Gateway, LLMError

    lines = [f"- [{t}] {it.title} ({it.feed})" for t, its in selection.items() for it in its]
    if not lines:
        return None
    try:
        return Gateway.from_env().chat(
            "Voici les titres de la semaine :\n" + "\n".join(lines) + "\n\nRésume en 3 points "
            "maximum ce qui compte pour un projet d'IA locale + électronique (ESP32, Arduino). "
            "N'invente rien : uniquement à partir des titres.",
            role="text",
            max_tokens=400,
        )
    except LLMError:
        return None


if __name__ == "__main__":  # pragma: no cover
    app()
