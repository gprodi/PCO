"""Inventaire par photo : vision IA -> validation/correction -> ajout au stock + retours (C10/C11)."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from microforge.app_streamlit.client import ApiError
from microforge.app_streamlit.ui import require_login, show_error

st.title("📷 Inventaire par photo")
c = require_login()

st.markdown("Pose tes composants sur un fond uni, bien éclairés, sans qu'ils se chevauchent.")
source = st.radio("Source", ["Appareil photo", "Fichier"], horizontal=True)
photo = (
    st.camera_input("Prendre la photo")
    if source == "Appareil photo"
    else st.file_uploader(
        "Photo (JPEG, PNG, WEBP — 8 Mo max.)", type=["jpg", "jpeg", "png", "webp"]
    )
)
location = st.text_input("Emplacement (ex. tiroir 2)", max_chars=80)

if photo is not None and st.button("Analyser la photo", type="primary"):
    with st.spinner("Analyse en cours (détection + identification)…"):
        try:
            st.session_state.scan = c.scan(
                photo.getvalue(), photo.name or "photo.jpg", photo.type or "image/jpeg"
            )
        except ApiError as exc:
            show_error(exc)

scan = st.session_state.get("scan")
if scan:
    st.caption(
        f"Mode : {scan['mode']} — modèle : {scan['model_version']} — {scan['latency_ms']} ms"
    )
    rows = [
        {
            "composant": i["component_id"],
            "libellé lu": i["label"],
            "quantité": i["quantity"],
            "confiance": round(i["confidence"], 2),
            "source": i["source"],
            "garder": True,
        }
        for i in scan["items"]
    ]
    rows += [
        {
            "composant": None,
            "libellé lu": i["label"],
            "quantité": i["quantity"],
            "confiance": round(i["confidence"], 2),
            "source": i["source"],
            "garder": False,
        }
        for i in scan["unknown"]
    ]
    st.markdown(
        "**Vérifie et corrige** (la colonne *composant* attend un identifiant du catalogue, ex. `dht22`) :"
    )
    edited = st.data_editor(
        pd.DataFrame(rows), num_rows="dynamic", use_container_width=True, key="scan_editor"
    )
    if st.button("Ajouter à mon stock"):
        items, feedback = [], []
        original = {i["component_id"]: i for i in scan["items"]}
        for _, row in edited.iterrows():
            cid = row["composant"]
            if not row["garder"] or not cid:
                if row["libellé lu"] and row["source"] in ("yolo", "vlm") and not row["garder"]:
                    feedback.append(
                        {
                            "kind": "false_positive",
                            "predicted_component_id": row["composant"],
                            "source": row["source"],
                        }
                    )
                continue
            items.append({"component_id": cid, "quantity": int(row["quantité"])})
            before = original.get(cid)
            kind = (
                "correct" if before else ("missed" if pd.isna(row.get("source")) else "wrong_label")
            )
            feedback.append(
                {
                    "kind": kind,
                    "predicted_component_id": before["component_id"] if before else None,
                    "corrected_component_id": cid,
                    "confidence": float(row["confiance"])
                    if not pd.isna(row["confiance"])
                    else None,
                    "source": row["source"] if row["source"] in ("yolo", "vlm") else "vlm",
                    "model_version": scan["model_version"],
                }
            )
        try:
            photo_id = c.post(
                "/v1/photos",
                json={
                    "sha256": scan["sha256"],
                    "width": scan["width"],
                    "height": scan["height"],
                    "model_version": scan["model_version"],
                },
            )["id"]
            c.post("/v1/inventory/bulk", json={"items": items, "location": location})
            for fb in feedback:
                c.post("/v1/feedback", json={**fb, "photo_id": photo_id})
            st.success(
                f"{len(items)} type(s) de composants ajoutés. Merci pour les {len(feedback)} retours !"
            )
            del st.session_state["scan"]
        except ApiError as exc:
            show_error(exc)
