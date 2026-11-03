"""Brouillon de synthèse Markdown (gabarit modele-synthese.md) — à relire et compléter par un humain."""

from __future__ import annotations

from datetime import UTC, datetime

from microforge.veille.rank import RELIABILITY
from microforge.veille.sources import FeedResult, Item

TITLES = {
    "T1": "Vision embarquée & VLM",
    "T2": "Outillage LLM local et sécurité",
    "T3": "Réglementation IA & données",
    "T4": "Accessibilité & éco-conception",
    "T5": "Écosystème maker",
}


def _entry(it: Item) -> str:
    day = (it.published or "")[:10] or "date inconnue"
    reliability = RELIABILITY.get(it.feed, 6 if "releases" in it.feed.lower() else 5)
    summary = (it.summary[:280] + "…") if len(it.summary) > 280 else it.summary
    return (
        f"### {it.title}\n"
        f"- **Quoi** : {summary or '(résumé absent du flux)'}\n"
        f"- **Source** : [{it.feed}, {day}]({it.link}) — fiabilité {reliability}/7"
        f" (score de pertinence {it.score})\n"
        "- **Impact pour MicroForge** : à compléter\n"
        "- **Action** : aucune / à tester / backlog\n"
    )


def draft(
    selection: dict[str, list[Item]], results: list[FeedResult], llm_summary: str | None = None
) -> str:
    year, week, _ = datetime.now(UTC).isocalendar()
    ok = [r for r in results if r.status == "ok"]
    failed = [r for r in results if r.status != "ok"]
    total = sum(len(r.items) for r in ok)
    lines = [
        "<!-- BROUILLON généré automatiquement : à relire, vérifier et noter avant diffusion -->",
        f"# Synthèse de veille — semaine {year}-{week:02d} (brouillon)",
        "",
        f"*Flux lus : {len(ok)}/{len(results)} — articles reçus : {total} — "
        f"généré le {datetime.now(UTC):%d/%m/%Y}*",
        "",
    ]
    if llm_summary:
        lines += ["## En bref (proposé par le modèle local, à vérifier)", llm_summary.strip(), ""]
    for theme, items in selection.items():
        lines.append(f"## {theme} — {TITLES[theme]}")
        lines += [_entry(it) for it in items] or ["*Rien de marquant cette semaine.*", ""]
    if failed:
        lines += [
            "## Flux en échec (à corriger dans sources.opml)",
            "",
            "| Flux | Erreur |",
            "|---|---|",
        ]
        lines += [f"| {r.feed.title} | {r.error.replace('|', '/')} |" for r in failed]
        lines.append("")
    lines.append(
        "*Accessibilité : document structuré par titres, liens explicites, aucune information "
        "portée par la seule couleur.*"
    )
    return "\n".join(lines) + "\n"
