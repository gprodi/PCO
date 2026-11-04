"""Atelier virtuel : brancher les composants d'un projet, puis le voir fonctionner (sans matériel)."""

from __future__ import annotations

import math

import streamlit as st
import streamlit.components.v1 as components
from microforge.core import get_catalog
from microforge.core.builder import ProjectBuilder
from microforge.sim import TranspileError, atelier_html, atelier_payload

CAT = get_catalog()
BUILDER = ProjectBuilder(CAT)

st.title("🔌 Atelier virtuel")
st.caption(
    "Choisis un projet : branche chaque composant sur la bonne broche (une erreur est expliquée), "
    "puis règle les capteurs et regarde le montage réagir. Simulation du comportement, sans matériel."
)

templates = sorted(CAT.templates.values(), key=lambda t: t.title)
col1, col2 = st.columns(2)
tpl = col1.selectbox("Projet", templates, format_func=lambda t: t.title)
boards = [b for b in CAT.boards_for_template(tpl.id) if CAT.template_fits(tpl.id, b)]
default = next((i for i, b in enumerate(boards) if b.id == "esp32-devkit-v1"), 0)
board = col2.selectbox("Carte", boards, index=default, format_func=lambda b: b.name)

result = BUILDER.build(BUILDER.spec_from_template(tpl.id, board.id))
errors = [i for i in result.issues if i.severity.value == "error"]
if errors:
    st.error(f"Montage impossible sur {board.name} : {errors[0].message}")
    st.stop()
try:
    payload = atelier_payload(CAT, result)
except TranspileError as exc:
    st.error(f"Ce projet ne peut pas encore être simulé : {exc}")
    st.stop()

rows = math.ceil(len(payload["parts"]) / 3)
components.html(atelier_html(payload), height=620 + 420 * rows, scrolling=True)
with st.expander("Code JavaScript exécuté par la simulation (traduit du C++ du projet)"):
    st.code(payload["code"], language="javascript")
