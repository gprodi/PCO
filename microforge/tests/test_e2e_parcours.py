"""Parcours de bout en bout dans un navigateur : api_data et api_ia lancés en local, puis
l'application Streamlit (preuve de concept) ou la PWA construite (``microforge/pwa/dist``).

Base SQLite jetable, clés JWT éphémères (MF_ENV=dev), modèle de langage simulé (LLM_CHAIN=fake) :
aucun service externe. Le navigateur est piloté par Playwright pour Node : tests/e2e/parcours.cjs
(Streamlit) et pwa/e2e/parcours-pwa.cjs (PWA). La PWA est servie avec les en-têtes de son image
nginx (politique CSP comprise) : une ressource bloquée par la CSP fait échouer le parcours.
Job CI dédié : ``uv run pytest -m e2e`` (``MF_E2E_STRICT=1`` : un prérequis absent est un échec).
"""

from __future__ import annotations

import functools
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import httpx
import pytest
from pwa_nginx import PWA, nginx_config_js, nginx_headers

pytestmark = pytest.mark.e2e

TESTS = Path(__file__).parent
APP = TESTS.parent / "src" / "microforge" / "app_streamlit"
SCRIPT = TESTS / "e2e" / "parcours.cjs"


def _missing(reason: str) -> None:
    """Prérequis absent : test ignoré en local, échec en CI (MF_E2E_STRICT=1)."""
    if os.environ.get("MF_E2E_STRICT") == "1":
        pytest.fail(reason)
    pytest.skip(reason)


def _playwright_available(cwd: Path) -> bool:
    if shutil.which("node") is None:
        return False
    probe = subprocess.run(
        ["node", "-e", "require('playwright')"], capture_output=True, check=False, cwd=cwd
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


class _Processes:
    """Services lancés pour un parcours : journaux dans le dossier du test, arrêt garanti."""

    def __init__(self, tmp_path: Path, env: dict[str, str]):
        self.tmp_path, self.env, self.procs, self.logs = tmp_path, env, [], []

    def start(self, name: str, cmd: list[str], cwd: Path) -> None:
        log = (self.tmp_path / f"{name}.log").open("w")
        self.logs.append(log)
        self.procs.append(
            subprocess.Popen(cmd, env=self.env, cwd=cwd, stdout=log, stderr=subprocess.STDOUT)
        )

    def stop(self) -> None:
        for proc in self.procs:
            proc.terminate()
        for proc in self.procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        for log in self.logs:
            log.close()


def _start_apis(tmp_path: Path, front_origin: str) -> tuple[_Processes, str, str]:
    """api_data et api_ia sur des ports libres ; ``front_origin`` est autorisée par CORS."""
    data_port, ia_port = _free_port(), _free_port()
    data_url, ia_url = f"http://127.0.0.1:{data_port}", f"http://127.0.0.1:{ia_port}"
    env = {
        **os.environ,
        "MF_ENV": "dev",
        "MF_DATABASE_URL": f"sqlite:///{tmp_path / 'e2e.db'}",
        "MF_API_DATA_URL": data_url,
        "MF_API_IA_URL": ia_url,
        "MF_CORS_ORIGINS": front_origin,
        "LLM_CHAIN": "fake",
    }
    procs = _Processes(tmp_path, env)
    uvicorn = [sys.executable, "-m", "uvicorn"]
    try:
        procs.start(
            "data", [*uvicorn, "microforge.api_data.main:app", "--port", str(data_port)], tmp_path
        )
        _wait(f"{data_url}/health")
        procs.start(
            "ia", [*uvicorn, "microforge.api_ia.main:app", "--port", str(ia_port)], tmp_path
        )
        _wait(f"{ia_url}/health")
    except BaseException:
        procs.stop()
        raise
    return procs, data_url, ia_url


@pytest.fixture
def stack(tmp_path):
    if not _playwright_available(TESTS):
        _missing("Playwright pour Node absent (npm install playwright)")
    st_port = _free_port()
    procs, _, _ = _start_apis(tmp_path, f"http://127.0.0.1:{st_port}")
    try:
        procs.start(
            "streamlit",
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
            APP,
        )
        _wait(f"http://127.0.0.1:{st_port}/_stcore/health")
        yield f"http://127.0.0.1:{st_port}"
    finally:
        procs.stop()


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


# --------------------------------------------------------------------------------------- PWA


def _serve_static(root: Path, port: int, headers) -> ThreadingHTTPServer:
    """Serveur statique qui ajoute les en-têtes de l'image nginx (CSP comprise) ; ``headers(path)``
    donne ceux du chemin demandé (le cadre /atelier/ a sa propre CSP)."""

    class Handler(SimpleHTTPRequestHandler):
        extensions_map: ClassVar[dict[str, str]] = {
            **SimpleHTTPRequestHandler.extensions_map,
            ".js": "text/javascript",
            ".webmanifest": "application/manifest+json",
            ".woff2": "font/woff2",
        }

        def end_headers(self):
            for name, value in headers(self.path.split("?", 1)[0]).items():
                self.send_header(name, value)
            self.send_header("Cache-Control", "no-cache")
            super().end_headers()

        def log_message(self, *args):  # pas de journal par requête
            pass

    handler = functools.partial(Handler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture
def pwa(tmp_path):
    if not (PWA / "dist" / "index.html").exists():
        _missing("PWA non construite (cd microforge/pwa && npm ci && npm run build)")
    if not _playwright_available(PWA):
        _missing("dépendances de la PWA absentes (cd microforge/pwa && npm ci)")
    # Le port de la PWA doit être connu avant les API : c'est l'origine autorisée par CORS.
    pwa_port = _free_port()
    procs, data_url, ia_url = _start_apis(tmp_path, f"http://127.0.0.1:{pwa_port}")
    server = None
    try:
        root = tmp_path / "pwa"
        shutil.copytree(PWA / "dist", root)
        (root / "config.js").write_text(nginx_config_js(data_url, ia_url), encoding="utf-8")
        server = _serve_static(root, pwa_port, lambda path: nginx_headers(data_url, ia_url, path))
        yield f"http://127.0.0.1:{pwa_port}/"
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        procs.stop()


def test_parcours_pwa_dans_un_navigateur(pwa, tmp_path):
    proc = subprocess.run(
        ["node", str(PWA / "e2e" / "parcours-pwa.cjs"), pwa, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        cwd=PWA,
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("{")]
    assert lines, proc.stdout[-2000:] + proc.stderr[-2000:]
    result = json.loads(lines[-1])
    assert result["ok"], json.dumps(result, ensure_ascii=False)
    names = [s["name"] for s in result["steps"]]
    assert names == [
        "inscription",
        "accueil",
        "stock",
        "explorer",
        "projet",
        "thème complet",
        "créer",
        "atelier",
        "copilote",
        "photo",
        "hors ligne",
    ]
    assert all(v == [] for v in result["a11y"].values())
    assert result["errors"] == []
