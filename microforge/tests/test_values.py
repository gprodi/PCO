"""Valeurs des passifs : saisie libre, séries E, code couleur (étape 3 — stock par valeur)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from microforge.core.values import (
    E12,
    colors_for,
    format_value,
    nearest,
    parse_value,
    series_values,
    value_from_colors,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("4k7", 4700.0),
        ("4.7k", 4700.0),
        ("4,7 kΩ", 4700.0),
        ("4700", 4700.0),
        ("10K", 10_000.0),
        ("1M", 1e6),
        ("220 ohms", 220.0),
        ("1R0", 1.0),
        ("100n", 1e-7),
        ("100nF", 1e-7),
        ("0,1 µF", 1e-7),
        ("2u2", 2.2e-6),
        ("22p", 22e-12),
        ("470uF", 470e-6),
        (47, 47.0),
        ("", None),
        ("abc", None),
        (None, None),
    ],
)
def test_parse_value(text, expected):
    got = parse_value(text)
    assert got == pytest.approx(expected) if expected is not None else got is None


def test_format_and_series():
    assert format_value(4700, "Ω") == "4,7 kΩ" and format_value(1e-7, "F") == "100 nF"
    assert format_value(220, "Ω") == "220 Ω" and format_value(0, "Ω") == "0 Ω"
    e12 = series_values("E12", 10, 1e6)
    assert len(e12) == 12 * 5 + 1 and e12[0] == 10 and e12[-1] == 1e6 and 4700 in e12
    assert series_values("E6", 1e-11, 1e-6)[0] == pytest.approx(1e-11)
    assert nearest(5000, e12) == 4700 and nearest(260, e12) == 270


@pytest.mark.parametrize(
    ("ohms", "bands", "colors"),
    [
        (4700, 4, ["jaune", "violet", "rouge", "or"]),
        (220, 4, ["rouge", "rouge", "marron", "or"]),
        (10_000, 4, ["marron", "noir", "orange", "or"]),
        (1, 4, ["marron", "noir", "or", "or"]),
        (4700, 5, ["jaune", "violet", "noir", "marron", "marron"]),
    ],
)
def test_color_code(ohms, bands, colors):
    tol = "marron" if bands == 5 else "or"
    assert colors_for(ohms, bands, tol) == colors
    value, tolerance = value_from_colors(colors)
    assert value == pytest.approx(ohms) and tolerance == (1.0 if bands == 5 else 5.0)


def test_color_code_errors():
    with pytest.raises(ValueError):
        colors_for(0)
    with pytest.raises(ValueError):
        value_from_colors(["rose", "noir", "rouge", "or"])
    with pytest.raises(ValueError):
        value_from_colors(["rouge", "rouge"])
    assert value_from_colors(["marron", "noir", "rouge"]) == (1000.0, 20.0)  # 3 anneaux : ±20 %


@given(st.sampled_from(E12), st.integers(min_value=0, max_value=5))
def test_color_code_round_trip_e12(mantissa, exp):
    ohms = round(mantissa * 10**exp, 6)
    assert value_from_colors(colors_for(ohms))[0] == pytest.approx(ohms)
