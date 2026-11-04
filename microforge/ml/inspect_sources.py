"""Inspecte des jeux de données candidats : licence, classes, volumes (exécuté sur un runner GitHub).

uv run --no-project --with huggingface_hub --with httpx --with pyyaml \
    python microforge/ml/inspect_sources.py microforge/ml/candidates.yaml > inspection.md

Rien n'est téléchargé en masse : fiches, fichiers de configuration et listes de fichiers seulement.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import httpx
import yaml

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
UA = {
    "User-Agent": "MicroForge-inspection/0.1 (projet pedagogique; +https://github.com/gprodi/PCO)"
}


def inspect_hf(repo: str) -> list[str]:
    from huggingface_hub import HfApi, hf_hub_download

    out = [f"### Hugging Face : `{repo}`"]
    try:
        info = HfApi().dataset_info(repo)
    except Exception as exc:
        return [*out, f"- introuvable : {type(exc).__name__} {exc}"[:300], ""]
    card = info.card_data.to_dict() if info.card_data else {}
    files = [s.rfilename for s in info.siblings or []]
    images = [f for f in files if f.lower().endswith(IMAGE_EXT)]
    out.append(f"- licence (fiche) : **{card.get('license')}** ; étiquettes : {card.get('tags')}")
    out.append(
        f"- fichiers : {len(files)} dont {len(images)} images ; parquet : "
        f"{sum(f.endswith('.parquet') for f in files)}"
    )
    out.append(f"- images par dossier : {dict(Counter(f.split('/')[0] for f in images))}")
    out.append(f"- exemples : {images[:5]}")
    for name in files:
        low = name.lower()
        if low in {"data.yaml", "dataset.yaml"} or low.endswith("/data.yaml"):
            data = yaml.safe_load(
                Path(hf_hub_download(repo, name, repo_type="dataset")).read_text()
            )
            out.append(f"- classes ({name}) : {data.get('names')}")
        if low.startswith("readme") and low.endswith((".md", ".txt")):
            text = Path(hf_hub_download(repo, name, repo_type="dataset")).read_text(
                errors="replace"
            )
            keep = [
                ln.strip()
                for ln in text.splitlines()
                if re.search(r"licen|cc[- ]by|source|roboflow|class|image|photo|provided", ln, re.I)
            ]
            out.append(f"- {name} (extraits) :")
            out += [f"  > {ln[:220]}" for ln in keep[:25]]
    return [*out, ""]


def inspect_mendeley(entry: dict) -> list[str]:
    ds, version = entry["id"], entry.get("version", 1)
    out = [f"### Mendeley Data : `{ds}` v{version}"]
    with httpx.Client(timeout=60, headers=UA, follow_redirects=True) as client:
        for url in (
            f"https://data.mendeley.com/public-api/datasets/{ds}",
            f"https://data.mendeley.com/public-api/datasets/{ds}/files?folder_id=root&version={version}",
        ):
            r = client.get(url)
            out.append(f"- GET {url} -> {r.status_code}")
            if r.status_code == 200 and "json" in r.headers.get("content-type", ""):
                body = r.json()
                if isinstance(body, dict):
                    out.append(
                        f"  - nom : {body.get('name')} ; licence : {json.dumps(body.get('data_licence') or body.get('licence'))[:300]}"
                    )
                    out.append(f"  - clés : {sorted(body)[:30]}")
                elif isinstance(body, list):
                    out.append(
                        f"  - {len(body)} fichiers : "
                        + ", ".join(f"{f.get('filename')} ({f.get('size')} o)" for f in body[:15])
                    )
        if entry.get("pmc"):
            url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{entry['pmc']}/fullTextXML"
            r = client.get(url)
            out.append(f"- article {entry['pmc']} (Europe PMC) -> {r.status_code}")
            if r.status_code == 200:
                text = re.sub(r"<[^>]+>", " ", r.text)
                text = re.sub(r"\s+", " ", text)
                for pattern in (
                    r"[^.]{0,200}(?:licen[cs]e|CC BY)[^.]{0,200}\.",
                    r"[^.]{0,160}(?:classes|class labels|categories)[^.]{0,400}\.",
                    r"[^.]{0,200}(?:Roboflow|Kaggle|collected|captured)[^.]{0,200}\.",
                    r"[^.]{0,120}(?:bounding box|annotat)[^.]{0,200}\.",
                ):
                    for m in list(re.finditer(pattern, text, re.I))[:4]:
                        out.append(f"  > {m.group(0).strip()[:450]}")
    return [*out, ""]


def main(path: str) -> None:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    lines = ["# Inspection des jeux de données candidats", ""]
    for repo in cfg.get("huggingface", []):
        lines += inspect_hf(repo)
    for entry in cfg.get("mendeley", []):
        lines += inspect_mendeley(entry)
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1])
