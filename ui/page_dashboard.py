"""Dashboard page: high level statistics and recent activity."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from vcard import database

from . import theme
from .common import status_badge


def render() -> None:
    theme.header(
        "Doctor Visiting Card Extraction",
        "Local OCR + rule based extraction - no data leaves this machine.",
    )

    s = database.stats()
    cols = st.columns(4)
    cards = [
        ("Batches", s["total_batches"], "processing runs recorded"),
        ("Records", s["total_records"], "doctor rows extracted"),
        ("Verified", s["verified"], "manually confirmed"),
        ("Needs review", s["needs_review"], "flagged for verification"),
    ]
    for col, (label, value, sub) in zip(cols, cards):
        with col:
            st.markdown(theme.metric_card(label, value, sub), unsafe_allow_html=True)

    st.write("")
    cols2 = st.columns(3)
    with cols2[0]:
        st.markdown(theme.metric_card("Possible duplicates", s["duplicates"],
                                      "matched name / contact"), unsafe_allow_html=True)
    with cols2[1]:
        st.markdown(theme.metric_card("Open batches", s["processing_batches"],
                                      "can be resumed"), unsafe_allow_html=True)
    with cols2[2]:
        st.markdown(theme.metric_card("Engine", "PaddleOCR", "fully offline"),
                    unsafe_allow_html=True)

    st.write("")
    st.subheader("Getting started")
    st.markdown(
        "1. Open **Process Cards** and upload JPG / JPEG / PNG visiting cards.\n"
        "2. Review the extracted fields side-by-side with the original image.\n"
        "3. Export verified rows to Excel (optionally mapping your own template)."
    )

    st.subheader("Recent batches")
    batches = database.list_batches()[:8]
    if not batches:
        st.info("No batches yet. Upload some cards to get started.")
        return
    rows = [
        {
            "Created": b["created_at"][:19],
            "Note": b["note"],
            "Status": b["status"],
            "Total": b["total"],
            "Processed": b["processed"],
            "Failed": b["failed"],
        }
        for b in batches
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
