"""Lecture des modèles nginx de l'image PWA (microforge/pwa/nginx), comme le fait envsubst au
démarrage du conteneur : en-têtes de sécurité et contenu de /config.js."""

from __future__ import annotations

import re
from pathlib import Path

PWA = Path(__file__).resolve().parent.parent / "pwa"


def _substitute(text: str, api_data: str, api_ia: str) -> str:
    return text.replace("${MF_PUBLIC_API_DATA_URL}", api_data).replace(
        "${MF_PUBLIC_API_IA_URL}", api_ia
    )


def nginx_headers(api_data: str, api_ia: str) -> dict[str, str]:
    """En-têtes ``add_header`` de securite.inc.template, variables MF_PUBLIC_* substituées."""
    text = (PWA / "nginx" / "securite.inc.template").read_text(encoding="utf-8")
    pairs = re.findall(r'^add_header (\S+) "([^"]*)" always;$', text, flags=re.M)
    return {name: _substitute(value, api_data, api_ia) for name, value in pairs}


def nginx_config_js(api_data: str, api_ia: str) -> str:
    """Corps de /config.js tel que nginx le renvoie (directive ``return 200`` de default.conf)."""
    text = (PWA / "nginx" / "default.conf.template").read_text(encoding="utf-8")
    match = re.search(r'location = /config\.js \{.*?return 200 "(.*?)";', text, flags=re.S)
    if match is None:
        raise ValueError("directive return 200 de /config.js introuvable")
    return _substitute(match.group(1).replace("\\n", "\n"), api_data, api_ia)
