"""Application : saisir un avis, le faire analyser, l'enregistrer, voir les derniers."""

import streamlit as st

from app import client

st.set_page_config(page_title="Avis clients", page_icon="💬")
st.title("💬 Avis clients")

with st.form("avis"):
    texte = st.text_area("Ton avis", max_chars=2000)
    envoye = st.form_submit_button("Analyser et enregistrer")

if envoye and texte.strip():
    try:
        pred = client.predict(texte)
        client.save(texte, pred["sentiment"], pred["score"])
        st.success(f"Sentiment : {pred['sentiment']} (confiance {pred['score']:.0%}, modèle {pred['modele']})")
    except client.ApiError as exc:
        st.error(f"Service indisponible : {exc}")

st.subheader("Derniers avis")
try:
    rows = client.latest()
    st.dataframe(rows, hide_index=True) if rows else st.info("Aucun avis pour l'instant.")
except client.ApiError as exc:
    st.warning(f"Liste indisponible : {exc}")
