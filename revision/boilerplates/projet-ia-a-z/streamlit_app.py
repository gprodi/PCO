"""Interface de chat : capture la question, appelle l'API d'IA, affiche la réponse. Aucune logique métier."""

import uuid

import streamlit as st

from commun.config import get_settings
from ui import client as api

st.set_page_config(page_title="Assistant", page_icon=":material/forum:", layout="centered")

if "client" not in st.session_state:
    st.session_state.client = api.ClientAPI(get_settings().ia_api_url)
    st.session_state.historique = []
    st.session_state.session = uuid.uuid4().hex
client: api.ClientAPI = st.session_state.client

with st.sidebar:
    st.header("Compte")
    if client.connecte:
        st.success("Connecté")
        if st.button("Se déconnecter"):
            client.deconnecter()
            st.session_state.historique = []
            st.rerun()
    else:
        mode = st.radio("Action", ["Connexion", "Inscription"], horizontal=True, label_visibility="collapsed")
        with st.form("compte"):
            email = st.text_input("Adresse e-mail")
            mot_de_passe = st.text_input("Mot de passe (12 caractères au moins)", type="password")
            valider = st.form_submit_button(mode)
        if valider:
            try:
                if mode == "Inscription":
                    client.inscrire(email, mot_de_passe)
                client.connecter(email, mot_de_passe)
                st.rerun()
            except api.ErreurAPI as erreur:
                st.error(str(erreur))

st.title("Assistant")
st.caption(f"Questions sur {get_settings().domaine} : réponses tirées de la base et du web, sources citées.")

for message in st.session_state.historique:
    with st.chat_message(message["role"]):
        st.markdown(message["texte"])
        if message.get("sources"):
            with st.expander(f"Sources ({len(message['sources'])})"):
                for numero, source in enumerate(message["sources"], start=1):
                    lien = f" — [lien]({source['url']})" if source.get("url") else ""
                    st.markdown(f"**[{numero}]** {source['titre']} ({source['type']}){lien}")
        if message.get("etapes"):
            st.caption(" → ".join(message["etapes"]) + f" · {message['fournisseur']}")

if question := st.chat_input("Votre question", disabled=not client.connecte):
    st.session_state.historique.append({"role": "user", "texte": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"), st.spinner("L'assistant réfléchit…"):
        try:
            reponse = client.poser(question, st.session_state.session)
        except api.ErreurAPI as erreur:
            st.error(str(erreur))
        else:
            st.session_state.historique.append(
                {
                    "role": "assistant",
                    "texte": reponse["reponse"],
                    "sources": reponse["sources"],
                    "etapes": reponse["etapes"],
                    "fournisseur": reponse["fournisseur"],
                }  # fmt: skip
            )
            st.rerun()
elif not client.connecte:
    st.info("Connectez-vous (barre latérale) pour poser une question.")
