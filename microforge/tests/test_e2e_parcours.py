"""Parcours de bout en bout dans un navigateur : api_data, api_ia et Streamlit lancés en local.

Base SQLite jetable, clés JWT éphémères (MF_ENV=dev), modèle de langage simulé (LLM_CHAIN=fake) :
aucun service externe. Le navigateur est piloté par tests/e2e/parcours.cjs (Playwright pour Node).
Job CI dédié : ``uv run pytest -m e2e``.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.e2e

TESTS = Path(__file__).parent
APP = TESTS.parent / "src" / "microforge" / "app_streamlit"
SCRIPT = TESTS / "e2e" / "parcours.cjs"


def _playwright_available() -> bool:
    if shutil.which("node") is None:
        return False
    probe = subprocess.run(
        ["node", "-e", "require('playwright')"], capture_output=True, check=False, cwd=TESTS
    )
    return probe.returncode == 0


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait(url: str, timeout: float = 90) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"service injoignable : {url}")


@pytest.fixture
def stack(tmp_path):
    if not _playwright_available():
        pytest.skip("Playwright pour Node absent (npm install playwright)")
    data_port, ia_port, st_port = _free_port(), _free_port(), _free_port()
    env = {
        **os.environ,
        "MF_ENV": "dev",
        "MF_DATABASE_URL": f"sqlite:///{tmp_path / 'e2e.db'}",
        "MF_API_DATA_URL": f"http://127.0.0.1:{data_port}",
        "MF_API_IA_URL": f"http://127.0.0.1:{ia_port}",
        "MF_CORS_ORIGINS": f"http://127.0.0.1:{st_port}",
        "LLM_CHAIN": "fake",
    }
    logs = {name: (tmp_path / f"{name}.log").open("w") for name in ("data", "ia", "streamlit")}
    procs = []

    def start(cmd, log, cwd):
        procs.append(subprocess.Popen(cmd, env=env, cwd=cwd, stdout=log, stderr=subprocess.STDOUT))

    try:
        uvicorn = [sys.executable, "-m", "uvicorn"]
        start(
            [*uvicorn, "microforge.api_data.main:app", "--port", str(data_port)],
            logs["data"],
            tmp_path,
        )
        _wait(f"http://127.0.0.1:{data_port}/health")
        start(
            [*uvicorn, "microforge.api_ia.main:app", "--port", str(ia_port)], logs["ia"], tmp_path
        )
        _wait(f"http://127.0.0.1:{ia_port}/health")
        start(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "Accueil.py",
                "--server.headless=true",
                f"--server.port={st_port}",
                "--browser.gatherUsageStats=false",
            ],
            logs["streamlit"],
            APP,
        )
        _wait(f"http://127.0.0.1:{st_port}/_stcore/health")
        yield f"http://127.0.0.1:{st_port}"
    finally:
        for proc in procs:
            proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        for log in logs.values():
            log.close()


def test_parcours_complet_dans_un_navigateur(stack, tmp_path):
    proc = subprocess.run(
        ["node", str(SCRIPT), stack, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        cwd=TESTS,
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("{")]
    assert lines, proc.stdout[-2000:] + proc.stderr[-2000:]
    result = json.loads(lines[-1])
    assert result["ok"], result
    names = [s["name"] for s in result["steps"]]
    assert names[:3] == ["inscription", "stock", "idees"]
    assert sum(n.startswith("onglet ") for n in names) == 8
    assert names[-2:] == ["explorer", "copilote"]
    assert result["errors"] == []
