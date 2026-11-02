"""Explorer par thème : plantes, intérieur, extérieur, sécurité… -> plein d'idées de projets."""

from __future__ import annotations

import streamlit as st
from microforge.app_streamlit.client import ApiError
from microforge.app_streamlit.ui import require_login, show_build, show_error

st.title("🧭 Explorer par thème")
c = require_login()
use_stock = st.toggle("Tenir compte de mon stock", value=True)
try:
    inventory = c.inventory_summary() if use_stock else None
    themes = c.explore(inventory)
except ApiError as exc:
    show_error(exc)
    st.stop()

if "theme" not in st.session_state:
    st.session_state.theme = None

# Grille des thèmes (boutons = navigation clavier native)
cols = st.columns(3)
for i, t in enumerate(themes):
    with cols[i % 3]:
        ready = sum(1 for idea in t["idees"] if idea.get("realisable"))
        label = f"{t['icone']} {t['titre']} — {len(t['idees'])} idées" + (
            f" ({ready} réalisables)" if use_stock else ""
        )
        if st.button(label, key=f"theme-{t['id']}", use_container_width=True):
            st.session_state.theme = t["id"]
            st.session_state.pop("build", None)

theme = next((t for t in themes if t["id"] == st.session_state.theme), None)
if theme is None:
    # Pas de thème choisi : on donne envie avec le parcours et la vitrine.
    try:
        insp = c.inspiration()
    except ApiError as exc:
        show_error(exc)
        st.stop()
    n = insp["chiffres"]
    m = st.columns(4)
    m[0].metric("Projets générables", n["modeles_generables"])
    m[1].metric("Idées", n["idees"])
    m[2].metric("Thèmes", n["themes"])
    m[3].metric("Composants connus", n["composants"])

    st.header("🪜 Parcours : de la première LED au robot autonome")
    for step in insp["parcours"]:
        with st.expander(f"Étape {step['etape']} — {step['titre']}", expanded=step["etape"] == 1):
            st.write(step["objectif"])
            st.caption("Tu apprends : " + ", ".join(step["notions"]))
            for p in step["projets"]:
                cols_p = st.columns([4, 1])
                cols_p[0].markdown(f"**{p['titre']}** {'★' * p['difficulte']} — {p['description']}")
                if cols_p[1].button("Générer", key=f"path-{step['etape']}-{p['id']}"):
                    with st.spinner("Génération du câblage, du code et du guide…"):
                        try:
                            st.session_state.build = c.generate(
                                template_id=p["id"], board="arduino-uno"
                            )
                        except ApiError as exc:
                            show_error(exc)

    st.header("🌍 Ce que les makers construisent vraiment")
    st.caption(
        "De vrais projets open source à base de microcontrôleurs, et par quoi commencer pour y arriver."
    )
    vcols = st.columns(2)
    for i, v in enumerate(insp["vitrine"]):
        with vcols[i % 2].container(border=True):
            st.markdown(f"**[{v['nom']}]({v['url']})** · {v['categorie']} · *{v['carte']}*")
            st.write(v["description"])
            st.caption("Pour t'y préparer : " + ", ".join(p["titre"] for p in v["commencer_par"]))
    if st.session_state.get("build"):
        st.divider()
        st.subheader(st.session_state.build["spec"]["title"])
        show_build(st.session_state.build, "path")
    st.stop()

st.header(f"{theme['icone']} {theme['titre']}")
st.caption(theme["description"])
for idx, idea in enumerate(theme["idees"]):
    with st.container(border=True):
        badges = ["★" * idea["difficulte"], "générable" if idea["generable"] else "conçu par l'IA"]
        if idea.get("wifi"):
            badges.append("Wi-Fi")
        if use_stock:
            badges.append(
                "✅ réalisable avec ton stock"
                if idea["realisable"]
                else "🛒 il manque : " + (", ".join(idea["manquants"]) or "une carte compatible")
            )
        st.markdown(f"**{idea['titre']}** — {' · '.join(badges)}")
        st.write(idea["description"])
        st.caption("Composants : " + ", ".join(idea["composants_noms"]))
        if st.button(
            "Générer le projet" if idea["generable"] else "Concevoir avec l'IA",
            key=f"idea-{theme['id']}-{idx}",
        ):
            with st.spinner("Génération du câblage, du code et du guide…"):
                try:
                    if idea["generable"]:
                        board = "esp32-devkit-v1" if idea.get("wifi") else None
                        st.session_state.build = c.generate(
                            template_id=idea["template"], board=board or "arduino-uno"
                        )
                    else:
                        goal = f"{idea['titre']} : {idea['description']}"
                        st.session_state.build = c.from_goal(
                            goal,
                            "esp32-devkit-v1" if idea.get("wifi") else None,
                            inventory,
                            idea["composants"],
                        )
                except ApiError as exc:
                    show_error(exc)

if st.session_state.get("build"):
    st.divider()
    st.subheader(st.session_state.build["spec"]["title"])
    show_build(st.session_state.build, "explore")
