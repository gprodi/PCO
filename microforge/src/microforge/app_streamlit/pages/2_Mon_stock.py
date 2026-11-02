"""Stock de l'utilisateur."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from microforge.app_streamlit.client import ApiError
from microforge.app_streamlit.ui import require_login, show_error

st.title("📦 Mon stock")
c = require_login()
items = c.get("/v1/inventory")
if not items:
    st.info("Ton stock est vide : commence par une photo !")
else:
    st.dataframe(
        pd.DataFrame(items)[["id", "component_id", "quantity", "location", "note"]],
        use_container_width=True,
        hide_index=True,
    )

with st.form("add"):
    st.subheader("Ajouter à la main")
    cid = st.text_input("Identifiant ou nom (ex. dht22, esp32-devkit-v1)")
    qty = st.number_input("Quantité", min_value=1, max_value=1000, value=1)
    loc = st.text_input("Emplacement")
    if st.form_submit_button("Ajouter"):
        try:
            c.post(
                "/v1/inventory",
                json={"component_id": cid.strip(), "quantity": int(qty), "location": loc},
            )
            st.rerun()
        except ApiError as exc:
            show_error(exc)

if items:
    to_delete = st.selectbox(
        "Supprimer une ligne",
        [None, *[i["id"] for i in items]],
        format_func=lambda i: "—" if i is None else f"#{i}",
    )
    if to_delete and st.button("Supprimer"):
        c.delete(f"/v1/inventory/{to_delete}")
        st.rerun()
