"""Thème de l'application Streamlit : polices auto-hébergées présentes et contrastes WCAG respectés."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "src" / "microforge" / "app_streamlit"
CONFIG = tomllib.loads((APP / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
THEME = CONFIG["theme"]


def luminance(hex_color: str) -> float:
    def channel(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_fonts_are_self_hosted_and_licensed():
    assert CONFIG["server"]["enableStaticServing"] is True
    faces = THEME["fontFaces"]
    assert {f["family"] for f in faces} == {"IBM Plex Sans", "Barlow Condensed", "IBM Plex Mono"}
    for face in faces:
        assert face["url"].startswith("app/static/"), face  # jamais de CDN tiers (RGPD)
        assert (APP / face["url"].removeprefix("app/")).is_file(), face["url"]
    for family in ("ibm-plex-sans", "ibm-plex-mono", "barlow-condensed"):
        licence = APP / "static" / "fonts" / f"OFL-{family}.txt"
        assert "SIL Open Font License" in licence.read_text(encoding="utf-8")
    for key in ("font", "headingFont", "codeFont"):
        assert THEME[key].split(",")[0] in {f["family"] for f in faces}


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_contrasts(mode):
    t = THEME[mode]
    assert contrast(t["textColor"], t["backgroundColor"]) >= 7
    assert contrast(t["textColor"], t["secondaryBackgroundColor"]) >= 7
    assert contrast(t["linkColor"], t["backgroundColor"]) >= 4.5
    assert contrast("#ffffff", t["primaryColor"]) >= 4.5  # texte des boutons principaux
    assert contrast(t["primaryColor"], t["backgroundColor"]) >= 3  # onglet actif, curseurs
    sidebar = THEME[mode]["sidebar"]
    assert contrast(t["textColor"], sidebar["backgroundColor"]) >= 7
