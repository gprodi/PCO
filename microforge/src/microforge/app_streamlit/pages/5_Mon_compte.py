"""Compte et droits RGPD."""

from __future__ import annotations

import json

import streamlit as st
from microforge.app_streamlit.ui import require_login

st.title("👤 Mon compte")
c = require_login()
me = c.get("/v1/users/me")
st.write(
    f"Pseudo : **{me['username']}** · Ville : {me['city'] or '—'} · Inscription : {me['created_at'][:10]}"
)
st.download_button(
    "⬇️ Exporter toutes mes données (JSON)",
    json.dumps(c.get("/v1/users/me/export"), ensure_ascii=False, indent=2),
    file_name="mes-donnees-microforge.json",
)
st.divider()
st.subheader("Supprimer mon compte")
st.caption("Suppression définitive du compte, du stock, des projets et des retours.")
if st.checkbox("Je comprends que cette action est irréversible") and st.button(
    "Supprimer définitivement", type="primary"
):
    c.delete("/v1/users/me")
    c.access = c.refresh_token = None
    st.success("Compte supprimé.")
