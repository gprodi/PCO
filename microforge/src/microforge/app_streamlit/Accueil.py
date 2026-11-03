"""Page d'accueil : connexion / inscription et présentation."""

from __future__ import annotations

import streamlit as st

from microforge.app_streamlit.client import ApiError
from microforge.app_streamlit.ui import client, show_error

st.set_page_config(page_title="MicroForge", page_icon="🔧", layout="wide")
st.title("🔧 MicroForge")
st.markdown(
    "**De la photo de ton stock électronique au montage soudé, programmé et simulé.**  \n"
    "Photographie tes composants, découvre ce que tu peux construire, et récupère le câblage, "
    "le guide de soudure, le code ESP32/Arduino et la simulation Wokwi."
)

c = client()
if c.logged_in:
    me = c.get("/v1/users/me")
    st.success(f"Connecté·e en tant que **{me['username']}**.")
    st.page_link("pages/1_Inventaire_photo.py", label="📷 Photographier mon stock")
    st.page_link("pages/3_Idees_de_projets.py", label="💡 Que puis-je construire ?")
    st.page_link("pages/4_Generer_un_projet.py", label="🛠️ Je veux construire…")
    st.page_link("pages/6_Copilote.py", label="🤖 Poser une question au copilote")
    if st.button("Se déconnecter"):
        c.logout()
        st.rerun()
    st.stop()

login_tab, register_tab = st.tabs(["Connexion", "Créer un compte"])
with login_tab, st.form("login"):
    username = st.text_input("Pseudo ou e-mail", autocomplete="username")
    password = st.text_input("Mot de passe", type="password", autocomplete="current-password")
    if st.form_submit_button("Se connecter"):
        try:
            c.login(username, password)
            st.rerun()
        except ApiError as exc:
            show_error(exc)

with register_tab, st.form("register"):
    st.caption(
        "Données minimales : pseudo, e-mail (chiffré), ville facultative. Suppression possible à tout moment."
    )
    r_user = st.text_input("Pseudo (3 à 40 caractères)")
    r_mail = st.text_input("E-mail", autocomplete="email")
    r_pass = st.text_input(
        "Mot de passe (10 caractères min., lettres et chiffres)",
        type="password",
        autocomplete="new-password",
    )
    r_city = st.text_input("Ville (facultatif)")
    r_consent = st.checkbox(
        "J'accepte que mes photos corrigées servent à améliorer le modèle (facultatif)"
    )
    if st.form_submit_button("Créer mon compte"):
        try:
            c.register(r_user, r_mail, r_pass, r_city, r_consent)
            c.login(r_user, r_pass)
            st.rerun()
        except ApiError as exc:
            show_error(exc)

st.divider()
st.caption(
    "ℹ️ Les contenus (code, câblage) sont générés automatiquement avec l'aide de l'IA : vérifie toujours le montage avant la mise sous tension."
)
