"""C12 — Tests automatisés du modèle : données, labellisation, cohérence des classes, porte de qualité."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml
from PIL import Image

ML = Path(__file__).parents[1] / "ml"
sys.path.insert(0, str(ML))

import dataset_checks as dc  # noqa: E402
import evaluate  # noqa: E402
from microforge.core import get_catalog  # noqa: E402

NAMES = dc.load_names(ML / "data" / "dataset.yaml")


def test_classes_consistent_with_vision_mapping_and_catalog():
    mapping = yaml.safe_load(
        (Path(__file__).parents[1] / "src/microforge/vision/classes.yaml").read_text()
    )["classes"]
    assert set(NAMES.values()) == set(mapping), "dataset.yaml et classes.yaml divergent"
    cat = get_catalog()
    for cls, cid in mapping.items():
        assert cat.resolve(cid) == cid, f"{cls} -> {cid} absent du catalogue"
    assert sorted(NAMES) == list(range(len(NAMES))), "identifiants de classes non contigus"


@pytest.mark.parametrize(
    ("line", "ok"),
    [
        ("3 0.5 0.5 0.2 0.3", True),
        ("3 0.5 0.5 0.2", False),
        ("99 0.5 0.5 0.2 0.3", False),
        ("3 1.5 0.5 0.2 0.3", False),
        ("3 0.5 0.5 0 0.3", False),
        ("x 0.5 0.5 0.2 0.3", False),
        ("-1 0.5 0.5 0.2 0.3", False),
    ],
)
def test_label_line_rules(line, ok):
    assert (dc.check_label_line(line, len(NAMES)) is None) is ok


def _img(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), color).save(path)


def make_dataset(root: Path, leak: bool = False, bad_label: bool = False) -> Path:
    for i, split in enumerate(("train", "val", "test")):
        for j in range(2):
            color = (i * 80, j * 100, 50)
            _img(root / "images" / split / f"{split}{j}.jpg", color)
            label = "3 0.5 0.5 0.4 0.4\n6 0.2 0.2 0.1 0.1\n"
            if bad_label and split == "val" and j == 0:
                label = "3 0.5 0.5 1.4 0.4\n"
            (root / "labels" / split).mkdir(parents=True, exist_ok=True)
            (root / "labels" / split / f"{split}{j}.txt").write_text(label)
    if leak:
        _img(root / "images" / "test" / "fuite.jpg", (0, 0, 50))  # identique à train0
        (root / "labels" / "test" / "fuite.txt").write_text("3 0.5 0.5 0.4 0.4\n")
    return root


def test_valid_dataset(tmp_path):
    report = dc.validate_dataset(make_dataset(tmp_path), NAMES, min_per_class=1)
    assert report.ok, report.errors
    assert report.images == {"train": 2, "val": 2, "test": 2}
    assert report.instances["esp32_devkit"] == 6
    assert any("sous-représentée" in w for w in report.warnings)


def test_dataset_detects_leak_bad_labels_and_missing(tmp_path):
    root = make_dataset(tmp_path, leak=True, bad_label=True)
    (root / "labels" / "train" / "train1.txt").unlink()
    report = dc.validate_dataset(root, NAMES)
    errors = " ".join(report.errors)
    assert "fuite" in errors and "non normalisées" in errors and "label manquant" in errors
    assert not report.ok


def test_missing_split(tmp_path):
    assert "split manquant" in " ".join(dc.validate_dataset(tmp_path, NAMES).errors)


@pytest.mark.parametrize(
    ("cand", "prod", "ok"),
    [(0.80, None, True), (0.80, 0.81, True), (0.70, 0.81, False), (0.90, 0.81, True)],
)
def test_promotion_gate(cand, prod, ok):
    assert evaluate.gate(cand, prod)[0] is ok


def test_report_markdown():
    md = evaluate.report_markdown({"mAP50": 0.8}, {"led": 0.5, "dht22": 0.9}, "✅ ok")
    assert "| mAP50 | 0.800 |" in md and md.index("led") < md.index("dht22")
