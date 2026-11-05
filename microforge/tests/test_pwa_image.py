"""Image Docker de la PWA : modèles nginx (CSP, config.js) et cohérence avec la construction Vite."""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest
from pwa_nginx import PWA, nginx_config_js, nginx_headers

API, IA = "https://api.exemple.org", "https://ia.exemple.org"


def test_csp_n_ouvre_que_les_deux_api():
    csp = nginx_headers(API, IA)["Content-Security-Policy"]
    directives = dict(d.strip().split(" ", 1) for d in csp.split(";"))
    assert directives["connect-src"] == f"'self' {API} {IA}"
    assert directives["script-src"] == "'self'"
    assert directives["frame-ancestors"] == "'none'"
    assert "unsafe-eval" not in csp
    # Seuls les attributs style (dessins Wokwi) sont permis en ligne ; ni script ni balise <style>.
    assert directives["style-src"] == "'self'"
    assert directives["style-src-attr"] == "'unsafe-inline'"
    assert [d for d, v in directives.items() if "unsafe-inline" in v] == ["style-src-attr"]
    # Schéma de câblage en data: et aperçu de la photo en blob:
    assert directives["img-src"] == "'self' data: blob:"


def test_entetes_de_securite():
    headers = nginx_headers(API, IA)
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Permissions-Policy"].startswith("camera=(self)")  # photo du stock


def test_config_js_declare_les_deux_api():
    js = nginx_config_js(API, IA)
    assert js == f"window.MF_CONFIG = {{ apiDataUrl: '{API}', apiIaUrl: '{IA}' }};\n"
    if shutil.which("node"):
        out = subprocess.run(
            [
                "node",
                "-e",
                f"globalThis.window = {{}}; {js}; console.log(JSON.stringify(window.MF_CONFIG))",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert json.loads(out) == {"apiDataUrl": API, "apiIaUrl": IA}


def test_seules_les_variables_publiques_sont_substituees():
    dockerfile = (PWA / "Dockerfile").read_text(encoding="utf-8")
    assert "NGINX_ENVSUBST_FILTER=^MF_PUBLIC_" in dockerfile
    templates = "".join(p.read_text(encoding="utf-8") for p in (PWA / "nginx").glob("*.template"))
    variables = set(re.findall(r"\$\{(\w+)\}", templates))
    assert variables == {"MF_PUBLIC_API_DATA_URL", "MF_PUBLIC_API_IA_URL"}
    for name in variables:  # valeur par défaut : le modèle reste valide sans variable fournie
        assert f"{name}=" in dockerfile


def test_config_js_charge_avant_l_application():
    html = (PWA / "index.html").read_text(encoding="utf-8")
    assert html.index('src="./config.js"') < html.index('src="./src/main.jsx"')
    assert "<script>" not in html  # aucun script en ligne (CSP script-src 'self')


@pytest.mark.parametrize("image", ["node:", "nginx:"])
def test_images_epinglees(image):
    dockerfile = (PWA / "Dockerfile").read_text(encoding="utf-8")
    tag = re.search(rf"FROM {image}(\S+)", dockerfile).group(1)
    assert re.match(r"\d+\.\d+\.\d+-alpine$", tag), tag
