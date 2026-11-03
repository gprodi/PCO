"""Outillage de veille (E2) : OPML, flux RSS/Atom (analyse durcie), classement, brouillon, CLI."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from microforge.veille.rank import score, select, themes_of
from microforge.veille.report import draft
from microforge.veille.sources import Feed, Item, fetch, parse_feed, read_opml

NOW = datetime(2026, 11, 3, 12, tzinfo=UTC)

RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>CERT-FR</title>
<item><title>Vuln&#233;rabilit&#233; dans LiteLLM (CERTFR-2026-AVI-0999)</title>
<link>https://www.cert.ssi.gouv.fr/avis/CERTFR-2026-AVI-0999/</link>
<pubDate>Mon, 02 Nov 2026 10:00:00 +0000</pubDate>
<description>&lt;p&gt;Une faille de s&#233;curit&#233; permet une ex&#233;cution de code.&lt;/p&gt;</description></item>
<item><title>Ancien avis</title><link>https://example.org/old</link>
<pubDate>Mon, 05 Oct 2026 10:00:00 +0000</pubDate></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Ollama releases</title>
<entry><title>v0.40.14</title>
<link rel="alternate" type="text/html" href="https://github.com/ollama/ollama/releases/tag/v0.40.14"/>
<updated>2026-11-03T08:00:00Z</updated><content type="html">Gemma 4 vision fixes, faster GGUF loading</content></entry>
</feed>"""

XXE = b"""<?xml version="1.0"?>
<!DOCTYPE rss [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<rss version="2.0"><channel><item><title>&xxe;</title><link>https://x.org/a</link></item></channel></rss>"""


def test_opml_feeds_have_themes():
    feeds = read_opml(Path(__file__).parents[1] / "veille" / "sources.opml")
    assert len(feeds) >= 14 and all(f.url.startswith("https://") for f in feeds)
    themes = {f.theme for f in feeds}
    assert {"T3", "T4", "T5"} <= themes and any("T1" in t for t in themes)


def test_rss_and_atom_parsing():
    rss = parse_feed(RSS, Feed("CERT-FR - avis", "u", "T3"))
    assert rss[0].title.startswith("Vulnérabilité dans LiteLLM") and "<p>" not in rss[0].summary
    assert rss[0].published == "2026-11-02T10:00:00+00:00"
    atom = parse_feed(ATOM, Feed("Ollama releases", "u", "T1/T2"))
    assert atom[0].link.endswith("v0.40.14") and atom[0].published.startswith("2026-11-03")


def test_summary_without_children_is_kept():
    """Régression : un élément lxml sans enfant est « faux » ; le résumé était ignoré."""
    rss = (
        "<rss><channel><item><title>t</title><link>https://x.org/s</link>"
        "<description>Résumé simple</description></item></channel></rss>"
    ).encode()
    (item,) = parse_feed(rss, Feed("f", "u", "T5"))
    assert item.summary == "Résumé simple"


def test_external_entities_are_not_resolved():
    (item,) = parse_feed(XXE, Feed("piège", "u", "T2"))
    assert "root:" not in item.title  # /etc/passwd jamais lu


def test_ranking_and_selection():
    items = parse_feed(RSS, Feed("CERT-FR - avis", "u", "T3")) + parse_feed(
        ATOM, Feed("Ollama releases", "u", "T1/T2")
    )
    assert "T2" in themes_of(items[0])  # « faille », « LiteLLM »
    sel = select(items, days=7, now=NOW)
    titles = [it.title for its in sel.values() for it in its]
    assert "Ancien avis" not in titles and len(titles) == 2  # hors fenêtre de 7 jours
    ollama = next(it for its in sel.values() for it in its if it.title == "v0.40.14")
    assert ollama.score > score(Item("Sans rapport", "", None, "", "Inconnu", "autre"), NOW)
    dup = select(items + items, days=7, now=NOW)
    assert sum(len(v) for v in dup.values()) == 2  # dédoublonnage par lien


def test_fetch_reports_failures_and_draft_lists_them(tmp_path):
    def handler(req: httpx.Request) -> httpx.Response:
        if "ollama" in req.url.path:
            return httpx.Response(200, content=ATOM)
        if "cassé" in str(req.url) or "broken" in req.url.path:
            return httpx.Response(200, content=b"<rss><unclosed>")
        return httpx.Response(404)

    feeds = [
        Feed("Ollama releases", "https://github.com/ollama/ollama/releases.atom", "T1/T2"),
        Feed("Flux cassé", "https://example.org/broken.xml", "T5"),
        Feed("Flux absent", "https://example.org/404.xml", "T4"),
    ]
    results = fetch(feeds, httpx.Client(transport=httpx.MockTransport(handler)))
    assert [r.status for r in results] == ["ok", "erreur", "erreur"]
    sel = select([it for r in results for it in r.items], days=30, now=NOW)
    md = draft(sel, results, llm_summary="1. Ollama 0.40.14 publié.")
    assert "brouillon" in md.lower() and "Flux lus : 1/3" in md
    assert (
        "[Ollama releases, 2026-11-03](https://github.com/ollama/ollama/releases/tag/v0.40.14)"
        in md
    )
    assert "| Flux absent | HTTPStatusError" in md and "En bref" in md


def test_cli_writes_draft_and_json(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from microforge.veille import cli

    opml = tmp_path / "s.opml"
    opml.write_text(
        '<opml version="2.0"><body><outline text="T2 - Outillage">'
        '<outline type="rss" text="Ollama releases" xmlUrl="https://github.com/ollama/ollama/releases.atom"/>'
        "</outline></body></opml>",
        encoding="utf-8",
    )
    real_fetch = cli.__dict__.get("fetch")
    assert real_fetch is None  # importé paresseusement dans la commande

    import microforge.veille.sources as sources

    monkeypatch.setattr(
        sources,
        "fetch",
        lambda feeds, http=None: [sources.FeedResult(feeds[0], "ok", parse_feed(ATOM, feeds[0]))],
    )
    out = tmp_path / "sortie"
    res = CliRunner().invoke(
        cli.app, ["--opml", str(opml), "--days", "3650", "--out", str(out), "--no-llm"]
    )
    assert res.exit_code == 0, res.output
    assert "1/1 flux lus" in res.output
    data = json.loads((out / "articles.json").read_text())
    assert data["flux"][0]["statut"] == "ok" and (out / "brouillon.md").exists()
