"""Image Docker de la PWA : modèles nginx (CSP, config.js) et cohérence avec la construction Vite."""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest
from pwa_nginx import ATELIER_PREFIX, PWA, nginx_config_js, nginx_headers

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


def _csp(path: str) -> dict[str, str]:
    csp = nginx_headers(API, IA, path)["Content-Security-Policy"]
    return dict(d.strip().split(" ", 1) for d in csp.split(";"))


def test_csp_du_cadre_de_l_atelier():
    """new Function (simulateur) permis dans le cadre isolé seulement, sans aucun accès réseau."""
    d = _csp("/atelier/index.html")
    assert d["script-src"] == "'self' 'unsafe-eval'"
    assert d["default-src"] == "'none'" and d["connect-src"] == "'none'"
    assert d["frame-ancestors"] == "'self'"  # affichable par l'application seulement
    assert d["form-action"] == "'none'" and d["base-uri"] == "'none'"
    assert [k for k, v in d.items() if "unsafe-inline" in v] == ["style-src-attr"]
    assert "unsafe-eval" not in nginx_headers(API, IA, "/")["Content-Security-Policy"]


def test_location_atelier_dans_nginx():
    conf = (PWA / "nginx" / "default.conf.template").read_text(encoding="utf-8")
    block = re.search(r"location /atelier/ \{(.*?)\}", conf, flags=re.S).group(1)
    assert "include /etc/nginx/conf.d/atelier.inc;" in block
    assert "securite.inc" not in block  # sinon deux CSP : la plus stricte bloquerait le simulateur
    assert ATELIER_PREFIX == "/atelier/"


@pytest.mark.parametrize("name", ["mfsim.js", "atelier.js", "atelier.css"])
def test_atelier_copies_identiques_au_simulateur(name):
    """public/atelier/ reprend les fichiers de microforge/src/microforge/sim/static (source unique)."""
    source = PWA.parent / "src" / "microforge" / "sim" / "static" / name
    copy = PWA / "public" / "atelier" / name
    assert copy.read_bytes() == source.read_bytes(), f"recopier {source} vers {copy}"


def test_cadre_sans_script_en_ligne():
    html = (PWA / "public" / "atelier" / "index.html").read_text(encoding="utf-8")
    assert "<script>" not in html and "style=" not in html
    for src in re.findall(r'<script src="([^"]+)"', html):
        assert not src.startswith(("http:", "https:", "//")), src  # tout est servi par le site
    frame = (PWA / "src" / "atelier-frame.jsx").read_text(encoding="utf-8")
    assert re.findall(r'sandbox="([^"]*)"', frame) == ["allow-scripts"]  # origine opaque


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
