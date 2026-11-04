"""Import des zips de jeux de photos posés à la racine (Roboflow) : extraction sûre et rapport."""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parents[1] / "ml"))

import importer_zips


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (200, 30, 30)).save(buf, "JPEG")
    return buf.getvalue()


def roboflow_zip(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("data.yaml", "names: ['DHT-11', 'HC-SR04', 'Servo SG90']\nnc: 3\n")
        zf.writestr(
            "README.dataset.txt",
            "# Blinduino > 2024-05-01\nhttps://universe.roboflow.com/laboratorio-c/blinduino-qaulp\n"
            "Provided by a Roboflow user\nLicense: CC BY 4.0\n",
        )
        for split, n in (("train", 3), ("valid", 1)):
            for i in range(n):
                zf.writestr(f"{split}/images/img{i}_jpg.rf.abc{i}.jpg", _jpeg())
                zf.writestr(f"{split}/labels/img{i}_jpg.rf.abc{i}.txt", "0 0.5 0.5 0.2 0.2\n")


def run(tmp_path: Path, capsys, *extra: str) -> str:
    code = importer_zips.main(
        [
            "--racine",
            str(tmp_path),
            "--sources",
            str(tmp_path / "sources"),
            "--configs",
            str(tmp_path / "configs"),
            *extra,
        ]
    )
    out = capsys.readouterr().out
    assert code == 0, out
    return out


def test_zip_is_extracted_and_described(tmp_path, capsys):
    roboflow_zip(tmp_path / "Blinduino.v2i.yolov8.zip")
    out = run(tmp_path, capsys)
    dest = tmp_path / "sources" / "blinduino-v2i-yolov8"
    assert (dest / "train" / "images").is_dir() and (dest / "data.yaml").exists()
    assert "['DHT-11', 'HC-SR04', 'Servo SG90']" in out
    assert (
        "License: CC BY 4.0" in out and "universe.roboflow.com/laboratorio-c/blinduino-qaulp" in out
    )
    assert "images : 4 {'train': 3, 'valid': 1}" in out and "labels YOLO : 4" in out


def test_existing_folder_is_never_overwritten(tmp_path, capsys):
    roboflow_zip(tmp_path / "jeu.zip")
    run(tmp_path, capsys)
    marker = tmp_path / "sources" / "jeu" / "data.yaml"
    marker.write_text("names: ['modifié à la main']\n")
    out = run(tmp_path, capsys)
    assert "déjà présent" in out and "modifié à la main" in marker.read_text()


@pytest.mark.parametrize("bad", ["../evil.txt", "/etc/evil.txt", "C:/evil.txt", "a/../../evil.txt"])
def test_dangerous_archives_are_refused(tmp_path, capsys, bad):
    with zipfile.ZipFile(tmp_path / "piege.zip", "w") as zf:
        zf.writestr("data.yaml", "names: [a]\n")
        zf.writestr(bad, "x")
    out = run(tmp_path, capsys)
    assert "**refusé**" in out
    assert not (tmp_path / "sources" / "piege").exists()
    assert not (tmp_path / "evil.txt").exists() and not (tmp_path.parent / "evil.txt").exists()


def test_apply_installs_prepared_source_yaml(tmp_path, capsys):
    roboflow_zip(tmp_path / "Blinduino.v2i.yolov8.zip")
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "blinduino-v2i-yolov8.yaml").write_text("nom: blinduino\n")
    roboflow_zip(tmp_path / "autre.zip")
    out = run(tmp_path, capsys, "--appliquer")
    assert (
        tmp_path / "sources" / "blinduino-v2i-yolov8" / "source.yaml"
    ).read_text() == "nom: blinduino\n"
    assert "autre : pas encore de correspondance" in out and "prepare.py" in out


def test_no_zip_found(tmp_path, capsys):
    code = importer_zips.main(["--racine", str(tmp_path), "--sources", str(tmp_path / "s")])
    assert code == 1 and "Aucun zip" in capsys.readouterr().out


def test_rejected_datasets_are_reported_not_installed(tmp_path, capsys):
    roboflow_zip(tmp_path / "PCB composants.v5i.yolov11.zip")
    (tmp_path / "configs").mkdir()
    ecartes = tmp_path / "ecartes.yaml"
    ecartes.write_text("pcb-composants-v5i-yolov11: >-\n  composants soudés\n  sur cartes\n")
    out = run(tmp_path, capsys, "--appliquer", "--ecartes", str(ecartes))
    assert "pcb-composants-v5i-yolov11 : écarté (composants soudés sur cartes)" in out
    assert not (tmp_path / "sources" / "pcb-composants-v5i-yolov11" / "source.yaml").exists()


def test_rejected_list_names_no_retained_dataset():
    rejected = importer_zips.load_rejected(importer_zips.ROOT / "microforge/ml/jeux_ecartes.yaml")
    retained = {p.stem for p in (importer_zips.ROOT / "microforge/ml/sources").glob("*.yaml")}
    assert rejected and not set(rejected) & retained
    assert all(len(reason) > 20 for reason in rejected.values())


def test_report_does_not_depend_on_filesystem_order(tmp_path, capsys, monkeypatch):
    roboflow_zip(tmp_path / "Blinduino.v2i.yolov8.zip")
    first = run(tmp_path, capsys)
    original = Path.rglob
    monkeypatch.setattr(
        Path, "rglob", lambda self, pattern: reversed(list(original(self, pattern)))
    )
    assert run(tmp_path, capsys).split("<!--")[0] == first.split("<!--")[0]
    assert "images : 4 {'train': 3, 'valid': 1}" in run(tmp_path, capsys)
