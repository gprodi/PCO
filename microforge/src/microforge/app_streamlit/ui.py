"""Éléments d'interface partagés (session, garde d'authentification, rendus accessibles)."""

from __future__ import annotations

import streamlit as st

from microforge.app_streamlit.client import ApiError, MicroForgeClient

SEVERITY_ICON = {"error": "⛔", "warning": "⚠️", "info": "ℹ️"}


def client() -> MicroForgeClient:
    if "mf_client" not in st.session_state:
        st.session_state.mf_client = MicroForgeClient()
    return st.session_state.mf_client


def require_login() -> MicroForgeClient:
    c = client()
    if not c.logged_in:
        st.warning("Connecte-toi d'abord depuis la page d'accueil.")
        st.stop()
    return c


def show_error(exc: ApiError) -> None:
    st.error(f"Erreur {exc.status} : {exc.detail}")


def show_issues(issues: list[dict]) -> None:
    """Affiche le contrôle électrique : icône + texte (jamais la couleur seule)."""
    if not issues:
        st.success("Contrôle électrique : aucun problème détecté.")
        return
    for issue in issues:
        icon = SEVERITY_ICON.get(issue["severity"], "")
        text = f"{icon} **{issue['severity'].upper()}** `{issue['code']}` — {issue['message']}"
        if issue.get("fix"):
            text += f"  \n*Correctif :* {issue['fix']}"
        {"error": st.error, "warning": st.warning}.get(issue["severity"], st.info)(text)


def show_build(build: dict, key: str) -> None:
    """Onglets : câblage, schéma, code, guide, Wokwi, KiCad, nomenclature."""
    files = build["files"]
    show_issues(build["issues"])
    tabs = st.tabs(
        [
            "Câblage",
            "Schéma",
            "Code",
            "Guide de soudure",
            "Simulation Wokwi",
            "KiCad",
            "Nomenclature",
            "Fiabilité & sources",
        ]
    )
    with tabs[0]:
        st.markdown(files["cablage.md"])
    with tabs[1]:
        # SVG passé en texte : Streamlit l'affiche tel quel (en octets, il passerait par Pillow -> erreur).
        st.image(
            files["cablage.svg"],
            caption="Schéma de câblage (texte alternatif intégré au SVG)",
        )
    with tabs[2]:
        for path, content in files.items():
            if path.endswith((".ino", "mf_components.h")) and not path.startswith("wokwi/"):
                st.markdown(f"**{path}**")
                st.code(content, language="cpp")
    with tabs[3]:
        st.markdown(files["guide-montage.md"])
    with tabs[4]:
        st.markdown(
            "1. Ouvre [wokwi.com](https://wokwi.com) et crée un projet pour ta carte.\n"
            "2. Remplace `diagram.json`, `sketch.ino` et ajoute `mf_components.h` + `libraries.txt`.\n"
            "3. Lance la simulation ▶️."
        )
        missing = build.get("files", {}).get("wokwi/diagram.json")
        st.code(missing or "", language="json")
    with tabs[5]:
        st.code(files["kicad/projet.net"], language="lisp")
    with tabs[6]:
        st.dataframe(build["bom"], use_container_width=True)
    with tabs[7]:
        readme = files.get("README.md", "")
        part = readme.split("## Niveau de vérification", 1)
        if len(part) == 2:
            st.markdown("## Niveau de vérification" + part[1].split("\n---", 1)[0])
        else:
            st.info(
                "Projet conçu par l'IA : pas de tutoriel de référence, vérifie le câblage avec soin."
            )
