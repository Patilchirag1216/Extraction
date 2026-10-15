"""Doctor Visiting Card Extraction - Streamlit entry point.

Run with:  streamlit run app.py
Then open: http://localhost:8501
"""
from __future__ import annotations

import os

# These flags must be set before PaddleOCR / PaddlePaddle are imported.
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

import streamlit as st  # noqa: E402

from vcard import config, database  # noqa: E402
from ui import (  # noqa: E402
    page_dashboard,
    page_export,
    page_history,
    page_process,
    page_review,
    theme,
)
from ui.common import ensure_state_defaults  # noqa: E402

PAGES = {
    "Dashboard": page_dashboard.render,
    "Process Cards": page_process.render,
    "Review & Edit": page_review.render,
    "Export to Excel": page_export.render,
    "History & Resume": page_history.render,
}


def main() -> None:
    st.set_page_config(
        page_title="Doctor Visiting Card Extraction",
        page_icon="🩺",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    theme.inject()
    ensure_state_defaults()
    database.init_db()

    with st.sidebar:
        st.markdown(
            "<div style='padding:6px 0 10px 0;'>"
            "<span style='font-size:1.25rem;font-weight:800;color:#1F4E78;'>🩺 Card Extractor</span>"
            "<br><span style='color:#6B7280;font-size:.8rem;'>Offline OCR &amp; extraction</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.radio("Navigation", list(PAGES.keys()), key="nav", label_visibility="collapsed")
        st.divider()
        st.caption("Engine: **PaddleOCR** (local)")
        st.caption("No images or data leave this machine.")

    page = st.session_state.get("nav", "Dashboard")
    PAGES.get(page, page_dashboard.render)()


if __name__ == "__main__":
    main()
