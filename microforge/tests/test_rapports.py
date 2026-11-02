"""Les contenus des rapports E1–E5 restent alignés sur les modèles officiels (aucune section orpheline)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("docx")
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "microforge" / "docs" / "rapports" / "generer_rapports.py"


def _module():
    spec = importlib.util.spec_from_file_location("generer_rapports", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("epreuve", ["E1", "E2", "E3", "E4", "E5"])
def test_report_fills_every_section(epreuve, tmp_path, capsys):
    from docx import Document

    out = _module().fill(epreuve, tmp_path)
    assert "sections sans titre correspondant" not in capsys.readouterr().out
    doc = Document(str(out))
    empty = [p.text for p in doc.paragraphs if p.text.strip() == "[À COMPLÉTER]"]
    assert not empty, f"{epreuve} : {len(empty)} section(s) du modèle sans contenu"
    headings = [p.text for p in doc.paragraphs if (p.style.name or "").startswith("Heading")]
    assert headings and all(h.strip() != "[À COMPLÉTER]" for h in headings)


def test_outline_lists_competences():
    plan = _module().outline("E1")
    assert [c["competence"] for c in plan] == ["C1", "C2", "C3", "C4", "C5"]
