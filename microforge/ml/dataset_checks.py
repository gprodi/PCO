"""Règles de validation du dataset (C12) — utilisées par les tests et par la chaîne CD.

Fonctions pures, sans dépendance à Ultralytics : exécutables partout (CI ubuntu).
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class DatasetReport:
    images: dict[str, int] = field(default_factory=dict)
    instances: Counter[str] = field(default_factory=Counter)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def load_names(dataset_yaml: Path) -> dict[int, str]:
    data = yaml.safe_load(dataset_yaml.read_text(encoding="utf-8"))
    return {int(k): v for k, v in data["names"].items()}


def check_label_line(line: str, n_classes: int) -> str | None:
    """Une ligne YOLO valide : « classe cx cy w h », classe entière connue, coordonnées dans ]0, 1]."""
    parts = line.split()
    if len(parts) != 5:
        return f"5 valeurs attendues, {len(parts)} trouvées"
    try:
        cls = int(parts[0])
        cx, cy, w, h = map(float, parts[1:])
    except ValueError:
        return "valeurs non numériques"
    if not 0 <= cls < n_classes:
        return f"classe {cls} hors [0, {n_classes - 1}]"
    if not all(0 <= v <= 1 for v in (cx, cy)) or not all(0 < v <= 1 for v in (w, h)):
        return "coordonnées hors de [0, 1] (non normalisées ?)"
    return None


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_dataset(root: Path, names: dict[int, str], min_per_class: int = 0) -> DatasetReport:
    """Formats, complétude, labellisation, doublons et fuites entre splits."""
    report = DatasetReport()
    seen: dict[str, str] = {}
    for split in ("train", "val", "test"):
        img_dir, lbl_dir = root / "images" / split, root / "labels" / split
        if not img_dir.exists():
            report.errors.append(f"split manquant : {split}")
            continue
        images = [p for p in sorted(img_dir.iterdir()) if p.suffix.lower() in IMAGE_EXT]
        report.images[split] = len(images)
        for img in images:
            h = file_hash(img)
            if h in seen:
                kind = "fuite" if seen[h] != split else "doublon"
                report.errors.append(f"{kind} : {img.name} déjà présente dans {seen[h]}")
            seen[h] = split
            lbl = lbl_dir / f"{img.stem}.txt"
            if not lbl.exists():
                report.errors.append(f"label manquant pour {split}/{img.name}")
                continue
            lines = [ln for ln in lbl.read_text().splitlines() if ln.strip()]
            if not lines:
                report.warnings.append(f"image sans objet (négative) : {split}/{img.name}")
            for i, line in enumerate(lines, 1):
                err = check_label_line(line, len(names))
                if err:
                    report.errors.append(f"{split}/{lbl.name}:{i} {err}")
                else:
                    report.instances[names[int(line.split()[0])]] += 1
    if min_per_class:
        for name in names.values():
            if report.instances[name] < min_per_class:
                report.warnings.append(
                    f"classe sous-représentée : {name} ({report.instances[name]})"
                )
    return report
