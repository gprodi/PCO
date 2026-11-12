"""Boilerplates copier : métadonnées cohérentes, rendu complet, projets générés valides et testés."""

from __future__ import annotations

import importlib.util
import json
import py_compile
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml
from revision.config import PATHS, referentiel, registry
from revision.site_export import _boilerplates

copier = pytest.importorskip("copier")

BOILERPLATES = sorted(p.name for p in PATHS.boilerplates.iterdir() if (p / "copier.yml").exists())
#: modules dont les tests du projet généré ont besoin (sinon ces tests sont ignorés, pas le rendu)
NEEDS = {
    "fastapi-jwt-sqlmodel": ["fastapi", "sqlmodel", "jwt", "argon2", "slowapi", "multipart"],
    "two-apis-streamlit": ["fastapi", "sqlmodel", "loguru", "streamlit", "pydantic_settings"],
    "streamlit-multipage": ["streamlit", "pandas"],
    "mlflow-minio": ["mlflow", "sklearn"],
    "prefect-docker": ["httpx"],
    "gha-ci-cd": ["fastapi", "httpx"],
    "prometheus-grafana-uptimekuma": ["fastapi", "prometheus_client", "yaml"],
    "loki-alloy": ["fastapi", "loguru", "yaml"],
    "uv-package": [],
    "collecte-multisource": [
        "httpx",
        "polars",
        "rapidfuzz",
        "bs4",
        "sqlalchemy",
        "pydantic_settings",
        "loguru",
    ],
    "rag-llm-local": ["httpx", "pydantic_settings", "loguru", "rapidfuzz"],
    "projet-ia-a-z": [
        "fastapi",
        "sqlmodel",
        "jwt",
        "argon2",
        "slowapi",
        "multipart",
        "httpx",
        "loguru",
        "streamlit",
        "pydantic_settings",
        "prometheus_client",
        "polars",
        "rapidfuzz",
        "bs4",
        "langgraph",
        "yaml",
    ],
}


def _ids(node, pattern: str) -> set[str]:
    found = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key in {"id", "code"} and isinstance(value, str) and re.fullmatch(pattern, value):
                found.add(value)
            found |= _ids(value, pattern)
    elif isinstance(node, list):
        for item in node:
            found |= _ids(item, pattern)
    return found


def _referenced(node) -> set[str]:
    out = set()
    if isinstance(node, dict):
        out |= set(node.get("boilerplates") or [])
        for value in node.values():
            out |= _referenced(value)
    elif isinstance(node, list):
        for item in node:
            out |= _referenced(item)
    return out


def test_every_referenced_boilerplate_exists():
    assert _referenced(referentiel()) <= set(BOILERPLATES)
    assert len(BOILERPLATES) >= 12


@pytest.mark.parametrize("name", BOILERPLATES)
def test_metadata_points_to_real_courses_and_competences(name):
    meta = yaml.safe_load((PATHS.boilerplates / name / "copier.yml").read_text(encoding="utf-8"))
    assert meta["_titre"] and len(meta["_description"]) > 40
    assert set(meta["_cours"]) <= set(registry()["courses"]), meta["_cours"]
    assert set(meta["_competences"]) <= _ids(referentiel(), r"C\d+"), meta["_competences"]
    assert meta["_templates_suffix"] == ".jinja"


def test_site_export_lists_files_and_metadata():
    exported = {b["id"]: b for b in _boilerplates(PATHS.boilerplates)}
    assert set(exported) == set(BOILERPLATES)
    jwt = exported["fastapi-jwt-sqlmodel"]
    assert "C5" in jwt["competences"] and "app/main.py" in jwt["fichiers"]
    assert "copier.yml" not in jwt["fichiers"]
    # Noms tels qu'ils apparaissent dans le projet généré, options signalées, aperçu choisi.
    starter = exported["projet-ia-a-z"]
    assert "README.md" in starter["fichiers"] and ".github/workflows/ci.yml" in starter["fichiers"]
    assert not any("{%" in f or f.endswith(".jinja") for f in starter["fichiers"])
    assert starter["options"]["docs/conf.py"] == "avec_docs"
    assert list(starter["apercu"])[:2] == ["README.md", "agents/pipeline.py"]


def test_bricks_share_the_starter_files():
    from revision.briques import ecarts

    assert ecarts() == [], "lancer : uv run python -m revision.briques"


def test_site_page_gives_a_working_copier_command():
    page = (PATHS.root / "revision/site/src/pages/boilerplates/[id].astro").read_text(
        encoding="utf-8"
    )
    assert "--subdirectory" not in page  # option inexistante dans copier
    assert "uvx copier copy PCO/revision/boilerplates/{b.id}" in page


def _render(name: str, dst: Path) -> Path:
    copier.run_copy(
        str(PATHS.boilerplates / name), str(dst), defaults=True, quiet=True, unsafe=False
    )
    return dst


@pytest.mark.parametrize("name", BOILERPLATES)
def test_rendered_project_is_complete_and_valid(name, tmp_path):
    out = _render(name, tmp_path / name)
    files = [p for p in out.rglob("*") if p.is_file()]
    assert files and not any(p.name == "copier.yml" for p in files)
    for path in files:
        rel = path.relative_to(out)
        assert "{{" not in str(rel) and not path.name.endswith(".jinja"), rel
        text = path.read_text(encoding="utf-8")
        # Les seules accolades doubles restantes appartiennent aux outils cibles
        # (GitHub Actions ${{ }}, Prometheus/Grafana {{ $labels }}, Prefect {{ image.image }}).
        for match in re.finditer(r"(?<!\$)\{\{\s*([\w.]+)", text):
            assert match.group(1) in {
                "route",
                "version",
                "image.image",
                "$labels.job",
            } or path.suffix in {
                ".yml",
                ".yaml",
                ".json",
            }, f"{rel} : variable non rendue {match.group(0)}"
        if path.suffix == ".py":
            py_compile.compile(str(path), doraise=True)
        elif path.suffix in {".yml", ".yaml"}:
            list(yaml.safe_load_all(text))
        elif path.suffix == ".json":
            json.loads(text)
        elif path.suffix == ".toml":
            tomllib.loads(text)


#: variantes rendues en plus des réponses par défaut (options désactivées)
VARIANTES = {
    "projet-ia-a-z": {
        "avec_orchestration": False,
        "avec_supervision": False,
        "avec_ci": False,
        "avec_docs": False,
    },
}
CAS = [(n, None) for n in BOILERPLATES] + [(n, v) for n, v in VARIANTES.items()]


@pytest.mark.parametrize(
    ("name", "data"), CAS, ids=[f"{n}{'-options' if d else ''}" for n, d in CAS]
)
def test_generated_project_passes_its_own_tests_and_lint(name, data, tmp_path):
    missing = [m for m in NEEDS[name] if importlib.util.find_spec(m) is None]
    if missing:
        pytest.skip(f"dépendances absentes de cet environnement : {missing}")
    out = tmp_path / name
    copier.run_copy(
        str(PATHS.boilerplates / name),
        str(out),
        data=data or {},
        defaults=True,
        quiet=True,
        unsafe=False,
    )
    if data:
        assert not (out / "docs").exists() and not (out / ".github").exists()
    tests = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=out,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert tests.returncode == 0, tests.stdout[-3000:] + tests.stderr[-2000:]
    ruff = shutil.which("ruff") or str(Path(sys.executable).parent / "ruff")
    lint = subprocess.run(
        [ruff, "check", "."], cwd=out, capture_output=True, text=True, check=False
    )
    assert lint.returncode == 0, lint.stdout[-2000:]
    # La CI des projets générés vérifie aussi la mise en forme : elle doit passer dès le départ.
    forme = subprocess.run(
        [ruff, "format", "--check", "."], cwd=out, capture_output=True, text=True, check=False
    )
    assert forme.returncode == 0, forme.stdout[-2000:]
