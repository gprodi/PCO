"""Copilote : questions libres sur le matériel, réponses citées à partir du catalogue (RAG)."""

from __future__ import annotations

import streamlit as st
from microforge.app_streamlit.client import ApiError
from microforge.app_streamlit.ui import require_login, show_error

MODES = {
    "llm": "Réponse rédigée par le modèle de langage à partir des sources ci-dessous.",
    "extractif": "Aucun modèle de langage joignable : passages du catalogue les plus proches.",
    "inconnu": "Rien d'assez proche dans le catalogue : le copilote préfère ne pas inventer.",
}

st.title("🤖 Copilote")
st.caption(
    "Posez une question sur un composant, une carte ou un projet. Le copilote répond à partir du "
    "catalogue MicroForge (le même que celui du câblage) et cite ses sources [n]."
)
st.info(
    "Vous échangez avec un **assistant d'intelligence artificielle** : il répond à partir du catalogue "
    "MicroForge et cite ses sources, mais vérifiez toujours un montage avant de le mettre sous tension "
    "(AI Act, article 50)."
)
c = require_login()
use_stock = st.toggle("Tenir compte de mon stock", value=True)
history: list[dict] = st.session_state.setdefault("copilot", [])


def show(answer: dict) -> None:
    st.markdown(answer["answer"])
    st.caption(f"{MODES[answer['mode']]} Index : {answer['index']}.")
    if answer["sources"]:
        with st.expander(f"Sources ({len(answer['sources'])})"):
            for s in answer["sources"]:
                mark = "✅" if s["cited"] else "·"
                link = f" — [lien]({s['url']})" if s["url"] else ""
                st.markdown(
                    f"{mark} **[{s['n']}] {s['title']}** ({s['kind']}, score {s['score']}){link}"
                )
                st.caption(s["excerpt"])


for turn in history:
    with st.chat_message("user"):
        st.markdown(turn["question"])
    with st.chat_message("assistant"):
        show(turn["answer"])

question = st.chat_input(
    "Ex. : Quelles broches I2C sur l'ESP32-C3 ? Le DS18B20 marche-t-il sur un C6 ?"
)
if question:
    with st.chat_message("user"):
        st.markdown(question)
    try:
        inventory = c.inventory_summary() if use_stock else None
        answer = c.copilot_ask(question, inventory or None)
    except ApiError as exc:
        show_error(exc)
        st.stop()
    with st.chat_message("assistant"):
        show(answer)
    history.append({"question": question, "answer": answer})
