import numpy as np
import pandas as pd
import streamlit as st

from lib.state import init_state

init_state()
st.title("📄 Données")

uploaded = st.file_uploader("Fichier CSV", type="csv")
if uploaded is not None:
    st.session_state.df = pd.read_csv(uploaded)
if st.button("Charger un jeu d'exemple"):
    rng = np.random.default_rng(0)
    st.session_state.df = pd.DataFrame(
        {
            "jour": range(1, 31),
            "ventes": rng.integers(20, 80, 30),
            "avis_positifs": rng.integers(5, 40, 30),
        }
    )

df = st.session_state.df
if df is None:
    st.info("Aucune donnée : importe un CSV ou charge l'exemple.")
else:
    st.dataframe(df, hide_index=True)
    numeric = list(df.select_dtypes("number").columns)
    if numeric:
        cols = st.multiselect("Colonnes à tracer", numeric, default=numeric[-1:])
        if cols:
            st.line_chart(df[cols])
