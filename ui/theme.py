"""Global CSS for a clean, modern dashboard look."""
from __future__ import annotations

import streamlit as st

CSS = """
<style>
:root {
    --brand: #1F4E78;
    --brand-light: #2E6DA4;
    --accent: #0FB5A0;
    --warn: #E8A33D;
    --danger: #D9534F;
    --ok: #3C9A5F;
    --muted: #6B7280;
}

.block-container { padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1400px; }

h1, h2, h3 { color: var(--brand); letter-spacing: -0.01em; }

.app-header {
    background: linear-gradient(100deg, #1F4E78 0%, #2E6DA4 55%, #0FB5A0 130%);
    color: white; padding: 18px 24px; border-radius: 14px;
    margin-bottom: 18px; box-shadow: 0 6px 20px rgba(31,78,120,.25);
}
.app-header h1 { color: white; margin: 0; font-size: 1.5rem; }
.app-header p { margin: 4px 0 0 0; opacity: .9; font-size: .92rem; }

.metric-card {
    background: white; border: 1px solid #E6EAF0; border-radius: 12px;
    padding: 16px 18px; box-shadow: 0 2px 8px rgba(16,24,40,.05);
    height: 100%;
}
.metric-card .label { color: var(--muted); font-size: .78rem; text-transform: uppercase;
    letter-spacing: .06em; font-weight: 600; }
.metric-card .value { color: var(--brand); font-size: 1.9rem; font-weight: 700; line-height: 1.2; }
.metric-card .sub { color: var(--muted); font-size: .8rem; }

.badge {
    display: inline-block; padding: 2px 10px; border-radius: 999px;
    font-size: .72rem; font-weight: 600; letter-spacing: .02em;
}
.badge-ok { background: #E5F4EB; color: #1E7A43; }
.badge-warn { background: #FDF3E2; color: #A96C12; }
.badge-danger { background: #FBE9E8; color: #B23B37; }
.badge-muted { background: #EEF1F5; color: #4B5563; }

.field-flag { color: #A96C12; font-size: .75rem; font-weight: 600; }
.conf-bar-bg { background: #EEF1F5; border-radius: 4px; height: 6px; width: 100%; }
.conf-bar { height: 6px; border-radius: 4px; }

.small-note { color: var(--muted); font-size: .82rem; }
div[data-testid="stSidebarNav"] { display: none; }
section[data-testid="stSidebar"] { background: #F7F9FC; }
</style>
"""


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def header(title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""<div class="app-header"><h1>{title}</h1>
        <p>{subtitle}</p></div>""",
        unsafe_allow_html=True,
    )


def metric_card(label: str, value, sub: str = "") -> str:
    return (
        f"""<div class="metric-card"><div class="label">{label}</div>
        <div class="value">{value}</div><div class="sub">{sub}</div></div>"""
    )


def badge(text: str, kind: str = "muted") -> str:
    return f'<span class="badge badge-{kind}">{text}</span>'
