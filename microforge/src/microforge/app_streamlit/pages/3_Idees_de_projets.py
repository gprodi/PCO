"""« Que puis-je construire ? » : suggestions classées à partir du stock."""

from __future__ import annotations

import streamlit as st
from microforge.app_streamlit.client import ApiError
from microforge.app_streamlit.ui import require_login, show_build, show_error

st.title("💡 Que puis-je construire ?")
c = require_login()
inventory = c.inventory_summary()
st.caption(f"Stock analysé : {sum(inventory.values())} composants ({len(inventory)} références).")

try:
    suggestions = c.suggest(inventory)
except ApiError as exc:
    show_error(exc)
    st.stop()

for s in suggestions:
    status = (
        "✅ réalisable maintenant"
        if s["feasible_now"]
        else f"🛒 il manque : {', '.join(f'{k}×{v}' for k, v in s['missing'].items()) or 'la carte'}"
    )
    with st.expander(f"{s['title']} — difficulté {'★' * s['difficulty']} — {status}"):
        st.write(s["description"])
        st.caption(f"Carte : {s['board_name']} · Notions : {', '.join(s['learning'])}")
        for w in s["warnings"]:
            st.warning(w)
        if st.button("Générer ce projet", key=f"gen-{s['template_id']}"):
            st.session_state.build = c.generate(template_id=s["template_id"], board=s["board"])
            st.session_state.build_key = s["template_id"]

if st.session_state.get("build"):
    st.divider()
    show_build(st.session_state.build, st.session_state.build_key)
