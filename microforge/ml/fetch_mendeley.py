"""Télécharge un jeu Mendeley Data après vérification de sa licence (CC BY exigée), puis l'extrait.

uv run --no-project --with httpx python microforge/ml/fetch_mendeley.py x5thzmkxhy 1 data/raw/iotkits
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import httpx

API = "https://data.mendeley.com/public-api/datasets"
UA = {"User-Agent": "MicroForge-collecte/0.2 (projet pedagogique; +https://github.com/gprodi/PCO)"}


def check_licence(meta: dict) -> str:
    licence = meta.get("data_licence") or {}
    text = json.dumps(licence)
    if "CC BY" not in text or "NC" in licence.get("short_name", ""):
        raise SystemExit(f"licence non retenue : {text[:300]}")
    return licence.get("short_name") or licence.get("full_name") or "CC BY"


def fetch(dataset: str, version: int, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=300, headers=UA, follow_redirects=True) as client:
        meta = client.get(f"{API}/{dataset}", params={"version": version}).raise_for_status().json()
        licence = check_licence(meta)
        files = client.get(
            f"{API}/{dataset}/files", params={"folder_id": "root", "version": version}
        )
        report = {
            "nom": meta.get("name"),
            "doi": (meta.get("doi") or {}).get("id"),
            "licence": licence,
            "fichiers": [],
        }
        for item in files.raise_for_status().json():
            url = item["content_details"]["download_url"]
            target = out / item["filename"]
            sha = hashlib.sha256()
            with client.stream("GET", url) as r, target.open("wb") as fh:
                r.raise_for_status()
                for chunk in r.iter_bytes(1 << 20):
                    fh.write(chunk)
                    sha.update(chunk)
            report["fichiers"].append(
                {
                    "nom": item["filename"],
                    "octets": target.stat().st_size,
                    "sha256": sha.hexdigest(),
                }
            )
            if target.suffix == ".zip":
                with zipfile.ZipFile(target) as zf:
                    for member in zf.namelist():  # extraction sûre : aucun chemin absolu ni « .. »
                        if member.startswith("/") or ".." in Path(member).parts:
                            raise SystemExit(f"chemin refusé dans l'archive : {member}")
                    zf.extractall(out / target.stem)
                target.unlink()
    (out / "provenance.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    return report


if __name__ == "__main__":
    print(
        json.dumps(
            fetch(sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])), ensure_ascii=False, indent=1
        )
    )
