"""Source scraping — boutique d'électronique française (prix TTC en euros, disponibilité).

Démarche conforme au critère C1 :
1. **contraintes** : lecture des CGU et du ``robots.txt`` (vérifié automatiquement), données
   publiques uniquement, aucune donnée personnelle, User-Agent identifié, délai entre requêtes ;
2. **téléchargement du HTML** des pages visées, archivé tel quel (``data/raw/shop/<date>/html/``) ;
3. **parsing** des pages archivées avec BeautifulSoup selon des sélecteurs CSS déclarés dans
   ``shops.yaml`` (à ajuster après inspection du site cible : les sélecteurs fournis sont un exemple).
"""

from __future__ import annotations

import hashlib
import re
import time
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import yaml
from bs4 import BeautifulSoup

from microforge.data_pipeline.base import ExtractionError, Extractor, RawPart, to_dict
from microforge.data_pipeline.extract._http import USER_AGENT, make_client


def load_shop_config(name: str) -> dict[str, Any]:
    text = (
        resources.files("microforge.data_pipeline")
        .joinpath("shops.yaml")
        .read_text(encoding="utf-8")
    )
    shops = yaml.safe_load(text)["shops"]
    if name not in shops:
        raise ExtractionError(f"Boutique inconnue : {name} (shops.yaml)")
    return shops[name]


def parse_listing(html: str, cfg: dict[str, Any], page_url: str) -> list[RawPart]:
    """Extrait les produits d'une page de résultats (fonction pure, testable hors ligne)."""
    soup = BeautifulSoup(html, "lxml")
    sel = cfg["selectors"]
    out = []
    for node in soup.select(sel["item"]):
        name_el = node.select_one(sel["name"])
        if name_el is None:
            continue
        price_el = node.select_one(sel["price"])
        link_el = node.select_one(sel.get("link", "a"))
        stock_el = node.select_one(sel["stock"]) if sel.get("stock") else None
        ref_el = node.select_one(sel["ref"]) if sel.get("ref") else None
        href = link_el.get("href") if link_el else None
        out.append(
            RawPart(
                source="shop",
                source_ref=(ref_el.get_text(strip=True) if ref_el else None)
                or (href or name_el.get_text(strip=True)),
                name=name_el.get_text(" ", strip=True),
                price=price_el.get_text(" ", strip=True) if price_el else None,
                currency="EUR",
                stock=stock_el.get_text(" ", strip=True) if stock_el else None,
                url=urljoin(page_url, href) if href else page_url,
                supplier=cfg["name"],
            )
        )
    return out


class ShopScraper(Extractor):
    source = "shop"
    kind = "scraping"

    def setup(self) -> None:
        self.cfg = self.params.get("config") or load_shop_config(self.params.get("shop", "exemple"))
        self.http = self.params.get("http") or make_client()
        self.delay = float(self.cfg.get("delay_s", 3))
        self.robots = RobotFileParser()
        robots_txt = self.params.get("robots_txt")
        if robots_txt is None:
            resp = self.http.get(urljoin(self.cfg["base_url"], "/robots.txt"))
            robots_txt = resp.text if resp.status_code == 200 else ""
        self.robots.parse(robots_txt.splitlines())

    def allowed(self, url: str) -> bool:
        return self.robots.can_fetch(USER_AGENT, url)

    def download(self, url: str, html_dir: Path) -> str | None:
        if not self.allowed(url):
            return None
        resp = self.http.get(url)
        resp.raise_for_status()
        html = resp.text
        name = hashlib.sha1(url.encode(), usedforsecurity=False).hexdigest()[:12] + ".html"
        (html_dir / name).write_text(html, encoding="utf-8")
        return html

    def extract(self) -> list[dict[str, Any]]:
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        html_dir = self.out_dir / self.source / day / "html"
        html_dir.mkdir(parents=True, exist_ok=True)
        records = []
        skipped = 0
        for query in self.params.get("queries") or self.cfg.get("queries", []):
            url = self.cfg["search_url"].format(query=re.sub(r"\s+", "+", query.strip()))
            html = self.download(url, html_dir)
            if html is None:
                skipped += 1
                continue
            for part in parse_listing(html, self.cfg, url):
                part.extra = {"query": query}
                records.append(to_dict(part))
            time.sleep(self.delay)
        if skipped:
            records.append({"_robots_skipped": skipped})
        return [r for r in records if "_robots_skipped" not in r]
