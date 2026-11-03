"""« Je veux construire… » : objectif libre (LLM) ou modèle du catalogue, puis tous les livrables."""

from __future__ import annotations

import streamlit as st
from microforge.app_streamlit.client import ApiError
from microforge.app_streamlit.ui import require_login, show_build, show_error

st.title("🛠️ Je veux construire…")
c = require_login()
boards = {b["id"]: b["name"] for b in c.get("/v1/boards")}
templates = {t["id"]: t["title"] for t in c.get("/v1/templates")}

mode = st.radio("Point de départ", ["Décrire mon idée", "Choisir un modèle"], horizontal=True)
board = st.selectbox(
    "Carte",
    [None, *boards],
    format_func=lambda b: "Choisie par MicroForge" if b is None else boards[b],
)

if mode == "Décrire mon idée":
    goal = st.text_area(
        "Décris ce que tu veux construire",
        placeholder="Ex. : une station qui mesure la température de ma serre et m'avertit si elle dépasse 35 °C",
    )
    use_stock = st.checkbox("Privilégier mon stock", value=True)
    if st.button("Concevoir le projet", type="primary") and goal:
        with st.spinner("L'IA choisit les composants, MicroForge câble et vérifie…"):
            try:
                inv = c.inventory_summary() if use_stock else None
                st.session_state.build = c.from_goal(goal, board, inv)
            except ApiError as exc:
                show_error(exc)
else:
    tid = st.selectbox("Modèle", list(templates), format_func=lambda t: templates[t])
    if st.button("Générer", type="primary"):
        try:
            st.session_state.build = c.generate(
                template_id=tid, board=board or "arduino-uno", owned_resistors=c.owned_resistors()
            )
        except ApiError as exc:
            show_error(exc)

build = st.session_state.get("build")
if build:
    st.subheader(build["spec"]["title"])
    st.write(build["spec"].get("description", ""))
    show_build(build, "goal")
    col1, col2 = st.columns(2)
    with col1:
        zip_bytes = c.bundle(spec=build["spec"])
        st.download_button(
            "⬇️ Télécharger le projet complet (.zip)",
            zip_bytes,
            file_name="microforge-projet.zip",
            mime="application/zip",
        )
    with col2:
        if st.button("💾 Sauvegarder dans mes projets"):
            p = c.post(
                "/v1/projects",
                json={
                    "title": build["spec"]["title"],
                    "board_id": build["spec"]["board"],
                    "template_id": build["spec"].get("template_id"),
                    "spec": build["spec"],
                },
            )
            st.session_state.last_project = p["id"]
            st.success("Projet sauvegardé.")
    if st.session_state.get("last_project"):
        sl = c.post("/v1/shopping-list", json={"project_id": st.session_state.last_project})
        st.subheader("🛒 Liste d'achat")
        st.markdown(sl["markdown"])
