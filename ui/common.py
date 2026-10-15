"""Shared UI helpers."""
from __future__ import annotations

import os
from typing import Dict, List, Optional

import cv2
import numpy as np
import streamlit as st

from vcard import config, database


def load_rgb(path: str) -> Optional[np.ndarray]:
    """Load an image as RGB for Streamlit, or None when missing/unreadable."""
    if not path or not os.path.exists(path):
        return None
    try:
        buf = np.frombuffer(open(path, "rb").read(), dtype=np.uint8)
        bgr = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if bgr is None:
            return None
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    except Exception:
        return None


def status_badge(status: str) -> str:
    mapping = {
        config.STATUS_VERIFIED: "ok",
        config.STATUS_NEEDS_REVIEW: "warn",
        config.STATUS_DUPLICATE: "danger",
        config.STATUS_PENDING: "muted",
        "completed": "ok",
        "completed_with_errors": "warn",
        "processing": "muted",
    }
    return mapping.get(status, "muted")


def confidence_html(conf: float, needs_verification: bool) -> str:
    pct = int(round(conf * 100))
    if conf >= 0.8:
        color = "#3C9A5F"
    elif conf >= config.VERIFY_THRESHOLD:
        color = "#E8A33D"
    else:
        color = "#D9534F"
    flag = ' <span class="field-flag">&#9888; verify</span>' if needs_verification else ""
    return (
        f'<div style="display:flex;align-items:center;gap:8px;margin-top:2px;">'
        f'<div class="conf-bar-bg" style="flex:1;max-width:120px;">'
        f'<div class="conf-bar" style="width:{pct}%;background:{color};"></div></div>'
        f'<span class="small-note">{pct}%</span>{flag}</div>'
    )


def batch_options() -> Dict[str, str]:
    """Return {label: batch_id} for a selectbox."""
    out: Dict[str, str] = {}
    for b in database.list_batches():
        label = f"{b['created_at'][:19]}  |  {b['note'] or 'batch'}  |  {b['processed']}/{b['total']}  [{b['status']}]"
        out[label] = b["id"]
    return out


def record_label(rec: Dict, index: int) -> str:
    name = rec["data"].get("doctor_name") or "(no name)"
    return f"{index}. {name}  -  {rec['source_file']}  [{rec['status']}]"


def ensure_state_defaults() -> None:
    st.session_state.setdefault("nav", "Dashboard")
    st.session_state.setdefault("overlays", {})
    st.session_state.setdefault("last_batch_id", None)
