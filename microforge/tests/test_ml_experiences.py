"""Registre des entraînements : cohérent, comparable, relié aux classes du dataset."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ML = Path(__file__).resolve().parents[1] / "ml"
sys.path.insert(0, str(ML))

import compare_runs as cr  # noqa: E402
import dataset_checks as dc  # noqa: E402

RUNS = cr.load()
CLASSES = set(dc.load_names(ML / "data" / "dataset.yaml").values())


@pytest.mark.parametrize("run", RUNS, ids=lambda r: r["id"])
def test_every_run_is_traceable_and_consistent(run):
    assert isinstance(run["github_run"], int) and run["commit"] and run["date"]
    assert run["epochs"] > 0 and run["imgsz"] > 0 and run["duree_h"] > 0
    for split in cr.SPLITS:
        block = run.get(split)
        if not block:
            continue
        for key in ("precision", "rappel", "map50", "map50_95"):
            assert 0 <= block[key] <= 1, (split, key)
        assert block["map50_95"] <= block["map50"]
        for cls, (n, m50, m5095) in block["par_classe"].items():
            assert cls in CLASSES, cls
            assert n is None or n >= 0
            assert 0 <= m5095 <= m50 <= 1, (split, cls)
        assert len(block["par_classe"]) <= run["classes"]


def test_summary_and_per_class_tables():
    md = cr.summary(RUNS)
    assert all(r["id"] in md for r in RUNS) and "0,974" in md and "0,692" in md
    table = cr.per_class_markdown(RUNS, "test")
    # Uno : présent dans les deux runs évalués sur le test, absent du premier (test perdu)
    assert "| arduino_uno | — | 0,995 (14) * | 0,995 (179) |" in table
    assert "| capacitor_ceramic | — | — | 0,040 (68) |" in table


def test_measurability_flag():
    rows = {r["classe"]: r for r in cr.per_class(RUNS, "test", min_objets=30)}
    assert rows["arduino_mega"]["runs"]["iotkits-v1"]["mesurable"] is True  # 49 objets
    assert rows["esp32_devkit"]["runs"]["complet-v1"]["mesurable"] is False  # 2 objets


def test_cli_json_and_duplicates(tmp_path, capsys):
    assert cr.main(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [r["id"] for r in data["runs"]] == [r["id"] for r in RUNS]
    assert set(data["par_classe"]) == set(cr.SPLITS)
    dup = tmp_path / "doublon.yaml"
    dup.write_text(yaml.safe_dump({"runs": [RUNS[0], RUNS[0]]}), encoding="utf-8")
    with pytest.raises(ValueError, match="double"):
        cr.load(dup)
