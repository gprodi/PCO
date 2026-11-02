"""Brouillon de synthèse hebdomadaire : FreshRSS (API Google Reader) -> LLM local -> Markdown.

    FRESHRSS_URL=http://localhost:8080 FRESHRSS_USER=gael FRESHRSS_API_PASSWORD=... \
    uv run python microforge/veille/veille_weekly.py --days 7

Le brouillon est écrit dans syntheses/brouillon-AAAA-SS.md : il DOIT être relu et corrigé
(vérification des sources, notation de fiabilité) avant diffusion.
"""

from __future__ import annotations

import argparse
import os
import time
from datetime import date
from pathlib import Path

import httpx
from llm_gateway import Gateway

HERE = Path(__file__).parent


def fetch_items(days: int) -> list[dict]:
    base = os.environ["FRESHRSS_URL"].rstrip("/") + "/api/greader.php"
    login = httpx.post(
        f"{base}/accounts/ClientLogin",
        data={"Email": os.environ["FRESHRSS_USER"], "Passwd": os.environ["FRESHRSS_API_PASSWORD"]},
        timeout=30,
    )
    login.raise_for_status()
    auth = dict(line.split("=", 1) for line in login.text.splitlines() if "=" in line)["Auth"]
    since = int(time.time()) - days * 86400
    resp = httpx.get(
        f"{base}/reader/api/0/stream/contents/reading-list",
        params={"n": 200, "ot": since},
        headers={"Authorization": f"GoogleLogin auth={auth}"},
        timeout=60,
    )
    resp.raise_for_status()
    return [
        {
            "titre": it.get("title"),
            "source": (it.get("origin") or {}).get("title"),
            "lien": (it.get("canonical") or [{}])[0].get("href"),
            "resume": (it.get("summary") or {}).get("content", "")[:600],
        }
        for it in resp.json().get("items", [])
    ]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=7)
    args = p.parse_args()
    items = fetch_items(args.days)
    plan = (HERE / "plan-de-veille.md").read_text(encoding="utf-8")
    template = (HERE / "modele-synthese.md").read_text(encoding="utf-8")
    prompt = (
        f"Plan de veille :\n{plan}\n\nArticles de la semaine (JSON) :\n{items}\n\n"
        f"Rédige un BROUILLON de synthèse en suivant exactement ce gabarit :\n{template}\n"
        "Ne garde que ce qui concerne les thématiques ; cite chaque source avec son lien ; "
        "n'invente aucune information ; écris en français clair."
    )
    draft = Gateway.from_env().chat(prompt, role="text", max_tokens=4096)
    year, week, _ = date.today().isocalendar()
    out = HERE / "syntheses" / f"brouillon-{year}-{week:02d}.md"
    out.write_text(
        "<!-- BROUILLON généré par IA : à relire et vérifier avant diffusion -->\n" + draft,
        encoding="utf-8",
    )
    print(f"Brouillon écrit : {out} ({len(items)} articles)")


if __name__ == "__main__":
    main()
