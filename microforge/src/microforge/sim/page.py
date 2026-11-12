"""Page HTML autonome de l'atelier (Streamlit, export, démo)."""

from __future__ import annotations

import json
from functools import cache
from importlib import resources
from typing import Any

#: @wokwi/elements (licence MIT) : dessins réalistes des cartes et composants. Sans réseau, l'atelier
#: retombe sur des dessins simples.
WOKWI_BUNDLE = (
    "https://cdn.jsdelivr.net/npm/@wokwi/elements@1.9.2/dist/wokwi-elements.bundle.min.js"
)


@cache
def _static(name: str) -> str:
    return resources.files("microforge.sim").joinpath(f"static/{name}").read_text(encoding="utf-8")


def atelier_assets() -> dict[str, str]:
    """Scripts et feuille de style de l'atelier, pour les intégrer dans une autre page."""
    return {
        "mfsim.js": _static("mfsim.js"),
        "missions.js": _static("missions.js"),
        "atelier.js": _static("atelier.js"),
        "atelier.css": _static("atelier.css"),
    }


def payload_json(payload: dict[str, Any]) -> str:
    """JSON insérable dans une balise <script> (« </ » neutralisé)."""
    return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")


def atelier_html(
    payload: dict[str, Any], wokwi_src: str | None = WOKWI_BUNDLE, theme: str = ""
) -> str:
    """Document HTML complet : atelier monté sur le projet ``payload`` (cf. ``atelier_payload``)."""
    assets = atelier_assets()
    title = str(payload.get("title", "Atelier")).replace("<", "&lt;")
    theme_attr = f' data-theme="{theme}"' if theme in {"light", "dark"} else ""
    loader = (
        f"var s = document.createElement('script'); s.src = {json.dumps(wokwi_src)};"
        " s.onload = go; s.onerror = go; document.head.appendChild(s); setTimeout(go, 5000);"
        if wokwi_src
        else "go();"
    )
    return f"""<!doctype html>
<html lang="fr"{theme_attr}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Atelier — {title}</title>
<style>
:root {{ --bg: #f4f7f5; --surface: #ffffff; --ink: #12201a; --muted: #4f5f57; --line: #d3ddd8;
  --accent: #17694f; --accent-ink: #ffffff; --accent-soft: #e2f1ea; --ok: #1d7a3a; --err: #b42318; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg: #0c1411; --surface: #131f1a;
  --ink: #e4eee8; --muted: #9db0a6; --line: #26382f; --accent: #4fc79c; --accent-ink: #05130d;
  --accent-soft: #173328; --ok: #6fd08c; --err: #f2786c; color-scheme: dark; }} }}
:root[data-theme="dark"] {{ --bg: #0c1411; --surface: #131f1a; --ink: #e4eee8; --muted: #9db0a6;
  --line: #26382f; --accent: #4fc79c; --accent-ink: #05130d; --accent-soft: #173328; --ok: #6fd08c;
  --err: #f2786c; color-scheme: dark; }}
body {{ margin: 0; padding: 12px 16px; background: var(--bg); color: var(--ink);
  font-family: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif; }}
h1 {{ font-size: 1.15rem; margin: 0 0 10px; }}
{assets["atelier.css"]}
</style>
</head>
<body>
<h1>Atelier — {title}</h1>
<div id="atelier"></div>
<script type="application/json" id="mf-payload">{payload_json(payload)}</script>
<script>{assets["mfsim.js"]}</script>
<script>{assets["missions.js"]}</script>
<script>{assets["atelier.js"]}</script>
<script>
(function () {{
  var started = false;
  function go() {{
    if (started) return;
    started = true;
    var payload = JSON.parse(document.getElementById("mf-payload").textContent);
    window.atelier = MFAtelier.mount(document.getElementById("atelier"), payload);
  }}
  {loader}
}})();
</script>
</body>
</html>
"""
