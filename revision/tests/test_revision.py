"""Tests du moteur de révision : ingestion multi-formats, génération (LLM simulé), cache, RAG, API, export."""

from __future__ import annotations

import json

import pytest
import yaml
from fastapi.testclient import TestClient
from llm_gateway import FakeProvider, Gateway
from revision.config import PATHS, referentiel, registry
from revision.generate import Generator, content_hash, verify_sources
from revision.ingest import chunk_markdown, convert_file
from revision.ingest.converters import (
    clean_markdown,
    convert_bytes,
    extract_base64_images,
    from_html,
)
from revision.schemas import CourseContent, Fiche, Question
from revision.store import VectorIndex

COURS = PATHS.cours


# ------------------------------------------------------------------ registre & référentiel
def test_registry_files_exist_and_referentiel_links():
    reg = registry()
    for slug, c in reg["courses"].items():
        assert c["theme"] in reg["themes"], slug
        assert (COURS / c["files"][0]).exists(), f"{slug}: {c['files'][0]}"
    ref = referentiel()
    assert [c["id"] for c in ref["competences"]] == [f"C{i}" for i in range(1, 22)]
    for comp in ref["competences"]:
        for slug in comp["cours"]:
            assert slug in reg["courses"], f"{comp['id']} -> {slug}"


# ------------------------------------------------------------------ ingestion
def test_markdown_base64_images_removed(tmp_path):
    md = "# Titre\n\nTexte\\_échappé {#ancre}\n\n![][image1]\n\n[image1]: <data:image/png;base64,iVBORw0KGgo=>\n"
    text, n = extract_base64_images(md)
    assert n == 1 and "base64" not in text
    clean = clean_markdown(text)
    assert "Texte_échappé" in clean and "{#ancre}" not in clean and "[image]" in clean
    _, n2 = extract_base64_images(md, tmp_path / "img")
    assert n2 == 1 and (tmp_path / "img" / "image1.png").exists()


def test_real_course_formats():
    horragor = convert_file(COURS / "HorRAGor BOT Partie 1.md")
    assert "data:image" not in horragor and len(horragor) < 20000  # 630 Ko -> texte utile
    pdf = convert_file(COURS / "MLOPS 0 PACKAGING.pdf")
    assert "## Page 1" in pdf and "pyproject" in pdf.lower()
    pptx = convert_file(COURS / "securiser-api-fastapi.pptx")
    assert "JWT" in pptx and pptx.startswith("## 1.")
    html = convert_file(COURS / "sqlmodel_presentation.html")
    assert "SQLModel" in html and "<script" not in html


def test_docx_ipynb_and_errors(tmp_path):
    import docx

    d = docx.Document()
    d.add_heading("Chapitre", level=1)
    d.add_paragraph("Contenu du cours.")
    d.save(tmp_path / "c.docx")
    assert "## Chapitre" in convert_file(tmp_path / "c.docx")
    nb = {
        "cells": [
            {"cell_type": "markdown", "source": ["# NB"]},
            {"cell_type": "code", "source": ["print(1)"]},
        ]
    }
    (tmp_path / "n.ipynb").write_text(json.dumps(nb))
    assert "```python\nprint(1)" in convert_file(tmp_path / "n.ipynb")
    with pytest.raises(ValueError):
        convert_file(tmp_path / "x.exe")
    assert "Bonjour" in convert_bytes(b"# T\n\nBonjour", "a.md")
    assert from_html(
        "<html><body><script>x</script><main><h1>T</h1><p>p</p></main></body></html>", is_raw=True
    ).startswith("# T")


def test_chunker_overlap_and_ids():
    md = "# A\n\n" + "x" * 4000 + "\n\n## B\n\ncourt"
    chunks = chunk_markdown("demo", md, max_chars=1800, overlap=200)
    assert [c.id for c in chunks][:2] == ["demo#0", "demo#1"]
    assert chunks[-1].heading == "B"
    assert len(chunks) == 4


# ------------------------------------------------------------------ schémas
def test_schema_validation():
    with pytest.raises(ValueError):
        Question(question="?", choix=["a", "b"], bonne=3)
    f = Fiche(titre="t", resume="r", competences=["C1", "C22", "X3", "c5"])
    assert f.competences == ["C1", "c5"]


# ------------------------------------------------------------------ génération
def fake_gateway() -> Gateway:
    fiche = {
        "titre": "MLflow",
        "resume": "Suivi des expériences.",
        "objectifs": ["tracer"],
        "notions": [{"terme": "run", "definition": "exécution"}],
        "points_cles": ["log_metric"],
        "code": [],
        "pieges": [],
        "competences": ["C11", "C13"],
        "sources": ["demo#0", "demo#99"],
    }

    def responder(req):
        if req.json_schema is None:  # chat libre
            return "Réponse fondée sur les passages [demo#0]."
        if "fiche de révision" in req.prompt:
            return fiche
        return None  # instance générée depuis le schéma

    return Gateway.fake(FakeProvider(responder=responder))


def test_generator_cache_and_source_verification(tmp_path):
    gw = fake_gateway()
    md = "# Demo\n\nMLflow trace les runs avec log_metric."
    chunks = chunk_markdown("demo", md)
    gen = Generator(gw, tmp_path)
    content = gen.generate("demo", "Demo", "mlops", md, chunks)
    assert content.origine == "llm" and content.fiche.sources == ["demo#0"]
    assert content.quiz.questions and content.podcast.repliques
    calls = len(gw.providers[0].calls)
    gen.generate("demo", "Demo", "mlops", md, chunks)  # cache
    assert len(gw.providers[0].calls) == calls
    assert json.loads((tmp_path / "demo" / "meta.json").read_text())["hash"] == content_hash(md)


def test_verify_sources_flags_unsourced():
    f = verify_sources(
        Fiche(titre="t", resume="r", sources=["x#1"]), chunk_markdown("demo", "# a\n\ntexte")
    )
    assert f.sources == [] and "à relire" in f.points_cles[0]


# ------------------------------------------------------------------ pipeline, index, RAG
def test_add_course_index_and_chat(tmp_path):
    from revision.pipeline import add_course, all_courses
    from revision.rag import chat, evaluate_answer, oral_questions

    gw = fake_gateway()
    src = tmp_path / "cours.md"
    src.write_text(
        "# Kubernetes\n\nUn Pod est la plus petite unité déployable. KEDA met à l'échelle selon une file."
    )
    content = add_course(src, "Kubernetes et KEDA", "mlops", gw, tmp_path / "content")
    assert content.slug == "kubernetes-et-keda"
    assert "kubernetes-et-keda" in all_courses(tmp_path / "content")
    index = VectorIndex.load(tmp_path / "content" / "_index.json")
    assert index.items and index.items[0]["course"] == "kubernetes-et-keda"
    ans = chat("Qu'est-ce qu'un Pod ?", index, gw)
    assert ans.citations and ans.citations[0]["course"] == "kubernetes-et-keda"
    qs = oral_questions("E3", gw, n=3, seed=1)
    assert qs.questions
    ev = evaluate_answer(
        qs.questions[0], "Je surveille la confiance et le taux de corrections.", gw
    )
    assert 0 <= ev.note <= 20


def test_vector_index_roundtrip(tmp_path):
    idx = VectorIndex(
        [
            {"id": "a#0", "course": "a", "heading": "h", "text": "t", "vector": [1.0, 0.0]},
            {"id": "b#0", "course": "b", "heading": "h", "text": "t", "vector": [0.0, 1.0]},
        ]
    )
    assert idx.search([0.9, 0.1], k=1)[0][1]["id"] == "a#0"
    assert idx.search([0.9, 0.1], k=2, courses=["b"])[0][1]["id"] == "b#0"
    idx.save(tmp_path / "i.json")
    assert len(VectorIndex.load(tmp_path / "i.json").items) == 2


# ------------------------------------------------------------------ seed & export
def test_seed_files_valid():
    """Chaque fichier seed est un cours complet et valide (schémas Pydantic)."""
    from revision.seed import load_seed

    seeds = sorted(PATHS.seed.glob("*.yaml"))
    for path in seeds:
        content = load_seed(path)
        assert content.slug in registry()["courses"], path.name
        assert len(content.quiz.questions) >= 5, path.name
        assert len(content.flashcards.cartes) >= 6, path.name
        assert content.exercices.exercices and content.podcast.repliques, path.name
        assert content.mindmap.markdown.lstrip().startswith("# "), path.name


def test_seed_loader_and_export(tmp_path):
    from revision.site_export import export

    from revision.seed import apply_seeds

    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    sample = {
        "fiche": {"titre": "MLflow", "resume": "r", "competences": ["C11"]},
        "qcm": [{"question": "q", "choix": ["a", "b", "c", "d"], "bonne": 1, "explication": "e"}],
        "flashcards": [{"recto": "r", "verso": "v"}],
        "exercices": [{"titre": "t", "enonce": "e", "corrige": "c"}],
        "mindmap": "# MLflow\n- runs",
        "podcast": [{"voix": "A", "texte": "Bonjour"}],
    }
    (seed_dir / "mlflow.yaml").write_text(yaml.safe_dump(sample, allow_unicode=True))
    assert apply_seeds(seed_dir, tmp_path / "content") == ["mlflow"]
    stats = export(site_data=tmp_path / "site", content_dir=tmp_path / "content")
    assert stats["with_content"] == 1 and stats["courses"] >= 36
    data = json.loads((tmp_path / "site" / "courses.json").read_text())
    assert any(c["slug"] == "mlflow" and c["disponible"] for c in data["courses"])
    assert (
        CourseContent.model_validate_json(
            (tmp_path / "site" / "content" / "mlflow.json").read_text()
        ).origine
        == "seed"
    )


# ------------------------------------------------------------------ API locale
@pytest.fixture
def api_client(tmp_path, monkeypatch):
    from revision import api

    monkeypatch.setattr(api, "content_dir", lambda: tmp_path)
    monkeypatch.setattr(api, "gateway", fake_gateway)
    monkeypatch.setattr(api, "export", lambda **kw: {})
    return TestClient(api.create_app())


def test_api_add_source_job_chat_and_oral(api_client):
    assert api_client.get("/health").json()["status"] == "ok"
    assert api_client.post("/chat", json={"question": "Bonjour ?"}).status_code == 409
    r = api_client.post(
        "/sources",
        files={
            "file": ("cours.md", b"# Docker\n\nUn conteneur isole un processus.", "text/markdown")
        },
        data={"theme": "mlops"},
    )
    assert r.status_code == 202
    job = api_client.get(f"/jobs/{r.json()['job_id']}").json()
    assert job["status"] == "done" and job["slug"] == "cours"
    assert (
        api_client.post(
            "/sources", files={"file": ("x.exe", b"MZ", "application/octet-stream")}
        ).status_code
        == 415
    )
    chat = api_client.post("/chat", json={"question": "Qu'est-ce qu'un conteneur ?"}).json()
    assert chat["citations"]
    oral = api_client.post("/oral-blanc/E1?n=2").json()
    assert oral["questions"]
    assert api_client.post("/oral-blanc/E9").status_code == 404
    ev = api_client.post(
        "/oral-blanc/evaluer",
        json={"question": oral["questions"][0], "answer": "Ma réponse détaillée."},
    )
    assert ev.status_code == 200
    assert api_client.get("/jobs/inconnu").status_code == 404


def test_cli_status_and_ingest(monkeypatch, tmp_path):
    from revision.cli import app
    from typer.testing import CliRunner

    res = CliRunner().invoke(app, ["status"])
    assert res.exit_code == 0 and "mlflow" in res.output
