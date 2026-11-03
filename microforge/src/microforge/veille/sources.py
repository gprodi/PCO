"""Lecture du fichier OPML et collecte des flux RSS 2.0 / RSS 1.0 (RDF) / Atom.

Analyse XML durcie (lxml) : entités externes désactivées, aucun accès réseau pendant l'analyse,
arbres géants refusés — un flux est une donnée externe non fiable (XXE, « billion laughs »).
"""

from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import httpx
from lxml import etree

USER_AGENT = "MicroForge-veille/0.1 (projet pedagogique; +https://github.com/gprodi/PCO)"
_TAGS = re.compile(r"<[^>]+>")
_THEME = re.compile(r"\b(T\d(?:/T\d)*)\b")


def safe_parser() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False, no_network=True, huge_tree=False, recover=False, load_dtd=False
    )


@dataclass
class Feed:
    title: str
    url: str
    theme: str  # « T3 », « T1/T2 »…


@dataclass
class Item:
    title: str
    link: str
    published: str | None
    summary: str
    feed: str
    theme: str
    score: float = 0.0
    themes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FeedResult:
    feed: Feed
    status: str  # ok | erreur
    items: list[Item] = field(default_factory=list)
    error: str = ""


def read_opml(path: Path) -> list[Feed]:
    root = etree.fromstring(path.read_bytes(), safe_parser())
    feeds = []
    for outline in root.iter("outline"):
        url = outline.get("xmlUrl")
        if not url:
            continue
        parent = outline.getparent()
        label = (parent.get("text") or "") if parent is not None else ""
        m = _THEME.search(label)
        feeds.append(Feed(outline.get("text") or url, url, m.group(1) if m else "autre"))
    return feeds


def _text(el: etree._Element | None) -> str:
    if el is None:
        return ""
    raw = "".join(el.itertext()) if len(el) else (el.text or "")
    return re.sub(r"\s+", " ", html.unescape(_TAGS.sub(" ", raw))).strip()


def _date(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)  # RSS : RFC 822
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))  # Atom : ISO 8601
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def parse_feed(content: bytes, feed: Feed) -> list[Item]:
    root = etree.fromstring(content, safe_parser())
    items = []
    for node in root.iter():
        tag = etree.QName(node).localname if isinstance(node.tag, str) else ""
        if tag not in ("item", "entry"):
            continue
        fields = {etree.QName(c).localname: c for c in node if isinstance(c.tag, str)}
        link = ""
        if "link" in fields:
            link_el = fields["link"]
            link = link_el.get("href") or (link_el.text or "").strip()
            for c in node:  # Atom : préférer rel="alternate"
                if (
                    isinstance(c.tag, str)
                    and etree.QName(c).localname == "link"
                    and c.get("rel", "alternate") == "alternate"
                    and c.get("href")
                ):
                    link = c.get("href")
                    break
        when = next(
            (
                _date(fields[k].text or "")
                for k in ("published", "pubDate", "updated", "date")
                if k in fields and fields[k].text
            ),
            None,
        )
        # Pas de « a or b » sur des éléments lxml : un élément sans enfant est « faux ».
        summary = _text(
            next((fields[k] for k in ("summary", "description", "content") if k in fields), None)
        )
        items.append(
            Item(
                title=_text(fields.get("title")) or "(sans titre)",
                link=link,
                published=when,
                summary=summary[:600],
                feed=feed.title,
                theme=feed.theme,
            )
        )
    return items


def fetch(feeds: list[Feed], http: httpx.Client | None = None) -> list[FeedResult]:
    client = http or httpx.Client(
        timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    )
    results = []
    for feed in feeds:
        try:
            resp = client.get(feed.url)
            resp.raise_for_status()
            results.append(FeedResult(feed, "ok", parse_feed(resp.content, feed)))
        except (httpx.HTTPError, etree.XMLSyntaxError, ValueError) as exc:
            results.append(FeedResult(feed, "erreur", error=f"{type(exc).__name__}: {exc}"[:200]))
    return results
