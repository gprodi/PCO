import streamlit as st

from lib import api
from lib.state import init_state

init_state()
st.title("🤖 Prédiction")

with st.form("predict"):
    text = st.text_area("Texte à analyser", max_chars=2000)
    submitted = st.form_submit_button("Analyser")

if submitted and text.strip():
    try:
        result = api.predict(text)
        st.session_state.history.append({"texte": text[:60], **result})
        st.metric("Sentiment", result["sentiment"], f"confiance {result['score']:.0%}")
        st.caption(f"Source : {result['source']}")
    except api.ApiError as exc:
        st.error(str(exc))

if st.session_state.history:
    st.subheader("Historique de la session")
    st.dataframe(st.session_state.history, hide_index=True)
