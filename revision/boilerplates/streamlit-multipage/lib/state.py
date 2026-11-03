"""État partagé entre les pages (st.session_state survit aux changements de page)."""

import streamlit as st

DEFAULTS = {"df": None, "history": []}


def init_state() -> None:
    for key, value in DEFAULTS.items():
        st.session_state.setdefault(key, value.copy() if isinstance(value, list) else value)
