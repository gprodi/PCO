"""Convertit un export COCO (Roboflow : <split>/_annotations.coco.json) en source YOLO pour prepare.py.

uv run python microforge/ml/coco_to_yolo.py data/raw/iotkits/32.v1i.coco data/sources/iotkits

Écrit <sortie>/<split>/images/*, <sortie>/<split>/labels/*.txt et data.yaml (noms des catégories) ;
affiche le nombre d'instances par catégorie (pour écrire la correspondance des classes).
"""

from __future__ import annotations

import json
import shutil
import sys
from collections import Counter
from pathlib import Path

import yaml


def convert(src: Path, out: Path) -> Counter:
    annotation_files = sorted(src.rglob("_annotations.coco.json"))
    if not annotation_files:
        raise SystemExit(f"aucun _annotations.coco.json sous {src}")
    names: dict[int, str] = {}
    counts: Counter = Counter()
    for ann_file in annotation_files:
        data = json.loads(ann_file.read_text(encoding="utf-8"))
        for cat in data["categories"]:
            names.setdefault(cat["id"], cat["name"])
    ordered = sorted(names)  # indices YOLO contigus dans l'ordre des identifiants COCO
    index = {cid: i for i, cid in enumerate(ordered)}
    for ann_file in annotation_files:
        data = json.loads(ann_file.read_text(encoding="utf-8"))
        split = ann_file.parent.name
        by_image: dict[int, list[dict]] = {}
        for ann in data["annotations"]:
            by_image.setdefault(ann["image_id"], []).append(ann)
        for img in data["images"]:
            w, h = img["width"], img["height"]
            lines = []
            for ann in by_image.get(img["id"], []):
                x, y, bw, bh = ann["bbox"]
                if bw <= 0 or bh <= 0:
                    continue
                cx, cy = min(max((x + bw / 2) / w, 0), 1), min(max((y + bh / 2) / h, 0), 1)
                lines.append(
                    f"{index[ann['category_id']]} {cx:.6f} {cy:.6f} {min(bw / w, 1):.6f} {min(bh / h, 1):.6f}"
                )
                counts[names[ann["category_id"]]] += 1
            (out / split / "images").mkdir(parents=True, exist_ok=True)
            (out / split / "labels").mkdir(parents=True, exist_ok=True)
            shutil.copy2(
                ann_file.parent / img["file_name"], out / split / "images" / img["file_name"]
            )
            (out / split / "labels" / Path(img["file_name"]).with_suffix(".txt").name).write_text(
                "\n".join(lines) + ("\n" if lines else "")
            )
    (out / "data.yaml").write_text(
        yaml.safe_dump({"names": [names[c] for c in ordered]}, allow_unicode=True), encoding="utf-8"
    )
    return counts


if __name__ == "__main__":
    counts = convert(Path(sys.argv[1]), Path(sys.argv[2]))
    print("| Catégorie | Instances |\n|---|---|")
    for name, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"| {name} | {n} |")
