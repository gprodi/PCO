"""Stock de l'utilisateur : composants par catégorie, passifs par valeur, lots en un clic."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from microforge.api_data.catalog_sync import CATEGORY_LABELS
from microforge.app_streamlit.client import ApiError
from microforge.app_streamlit.ui import require_login, show_error
from microforge.core import get_catalog
from microforge.core.kits import KITS
from microforge.core.values import (
    COLORS,
    MULTIPLIER,
    colors_for,
    format_value,
    parse_value,
    value_from_colors,
)

CAT = get_catalog()

st.title("📦 Mon stock")
c = require_login()


def unit_of(component_id: str) -> str:
    comp = CAT.components.get(component_id)
    return comp.parametric.unit if comp and comp.parametric else ""


def name_of(component_id: str) -> str:
    item = CAT.components.get(component_id) or CAT.boards.get(component_id)
    return item.name if item else component_id


items = c.get("/v1/inventory")
if not items:
    st.info("Ton stock est vide : photographie tes tiroirs ou ajoute un lot ci-dessous.")
else:
    rows = [
        {
            "n°": i["id"],
            "composant": name_of(i["component_id"]),
            "valeur": format_value(i["value"], unit_of(i["component_id"]))
            if i.get("value")
            else "",
            "quantité": i["quantity"],
            "emplacement": i["location"],
        }
        for i in items
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(f"{sum(i['quantity'] for i in items)} pièces, {len(items)} lignes.")

# ------------------------------------------------------------------ ajout à la main
st.subheader("Ajouter un composant")
categories = {k: v for k, v in CATEGORY_LABELS.items() if k != "carte"}
col1, col2 = st.columns(2)
cat = col1.selectbox(
    "Catégorie",
    ["carte", *categories],
    format_func=lambda k: "Cartes microcontrôleurs" if k == "carte" else categories[k],
)
choices = (
    sorted(CAT.boards, key=lambda b: CAT.boards[b].name)
    if cat == "carte"
    else sorted(
        (cid for cid, comp in CAT.components.items() if comp.category == cat),
        key=lambda cid: CAT.components[cid].name,
    )
)
cid = col2.selectbox("Composant (tape pour chercher)", choices, format_func=name_of)
comp = CAT.components.get(cid)
value = 0.0
if comp and comp.parametric:
    allowed = comp.parametric.allowed()
    unit = comp.parametric.unit
    default = comp.parametric.default if comp.parametric.default in allowed else allowed[0]
    picked = st.selectbox(
        f"Valeur ({unit})",
        [*allowed, None],
        index=allowed.index(default) if default in allowed else 0,
        format_func=lambda v: "autre valeur…" if v is None else format_value(v, unit),
    )
    if picked is None:
        typed = st.text_input("Valeur libre (ex. 4k7, 2u2, 330)")
        value = parse_value(typed) or 0.0
    else:
        value = picked
col3, col4 = st.columns(2)
qty = col3.number_input("Quantité", min_value=1, max_value=1000, value=1)
loc = col4.text_input("Emplacement (tiroir, boîte…)")
if st.button("Ajouter au stock", type="primary"):
    try:
        c.post(
            "/v1/inventory",
            json={"component_id": cid, "value": value, "quantity": int(qty), "location": loc},
        )
        st.rerun()
    except ApiError as exc:
        show_error(exc)

# ------------------------------------------------------------------ lots
st.subheader("Ajouter un lot en un clic")
st.caption("Les assortiments courants des boutiques, pour démarrer sans tout saisir.")
kit_loc = st.text_input("Emplacement du lot", value="boîte d'assortiment", key="kit-loc")
for kit_id, kit in KITS.items():
    lines = kit["lignes"]
    label = f"{kit['titre']} — {len(lines)} lignes, {sum(x['quantity'] for x in lines)} pièces"
    if st.button(label, key=f"kit-{kit_id}"):
        try:
            c.post("/v1/inventory/bulk", json={"items": lines, "location": kit_loc})
            st.success(f"Lot ajouté : {kit['titre']}")
            st.rerun()
        except ApiError as exc:
            show_error(exc)

# ------------------------------------------------------------------ code couleur
with st.expander("🎨 Code couleur des résistances"):
    tab_v, tab_c = st.tabs(["Valeur → couleurs", "Couleurs → valeur"])
    with tab_v:
        typed = st.text_input("Valeur", value="4k7", key="cc-val")
        bands = st.radio("Anneaux", [4, 5], horizontal=True)
        ohms = parse_value(typed)
        if ohms:
            try:
                tol = "marron" if bands == 5 else "or"
                st.write(" · ".join(colors_for(ohms, bands, tol)))
            except ValueError as exc:
                st.warning(str(exc))
        else:
            st.caption("Exemples : 220, 4k7, 10k, 1M")
    with tab_c:
        digits = st.columns(3)
        c1 = digits[0].selectbox("1er anneau", COLORS, index=4)
        c2 = digits[1].selectbox("2e anneau", COLORS, index=7)
        c3 = digits[2].selectbox("Multiplicateur", list(MULTIPLIER), index=2)
        ohms, tolerance = value_from_colors([c1, c2, c3, "or"])
        st.write(f"**{format_value(ohms, 'Ω')}** ± {tolerance:g} %")

# ------------------------------------------------------------------ suppression
if items:
    to_delete = st.selectbox(
        "Supprimer une ligne",
        [None, *[i["id"] for i in items]],
        format_func=lambda i: "—" if i is None else f"#{i}",
    )
    if to_delete and st.button("Supprimer"):
        c.delete(f"/v1/inventory/{to_delete}")
        st.rerun()
