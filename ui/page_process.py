"""Upload & process page: batch OCR extraction with live progress."""
from __future__ import annotations

import glob
import os
import uuid

import streamlit as st

from vcard import config, database, pipeline

from . import theme
from .common import status_badge


def _sample_files():
    files = []
    for path in sorted(glob.glob(os.path.join(config.SAMPLE_DIR, "*.png"))):
        files.append({"name": os.path.basename(path), "path": path})
    return files


def _run(files, options, note, batch_id):
    database.init_db()
    # Pre-create the batch so the file list is stored for resume.
    database.create_batch(
        batch_id,
        note=note,
        total=len(files),
        options={"preproc": options, "files": files},
    )

    bar = st.progress(0.0, text="Starting...")
    status = st.empty()

    def progress(i, n, name, state):
        frac = i / max(1, n)
        labels = {
            "ok": "extracted",
            "failed": "failed",
            "skipped": "skipped (already done)",
        }
        bar.progress(frac, text=f"[{i}/{n}] {name}: {labels.get(state, state)}")
        status.caption(f"Processed {i} of {n} images")

    summary = pipeline.process_batch(
        files, batch_id, options=options, note=note,
        progress=progress, collect_overlays=True,
    )
    bar.progress(1.0, text="Done")
    st.session_state["last_batch_id"] = batch_id
    st.session_state["overlays"] = summary.get("overlays", {})
    st.session_state["last_summary"] = summary
    return summary


def _show_summary(summary):
    st.success(
        f"Batch complete - {summary['processed']} processed, "
        f"{summary['duplicates']} possible duplicate(s), "
        f"{summary['failed']} failed, {summary['skipped']} skipped."
    )
    cols = st.columns(4)
    cols[0].metric("Processed", summary["processed"])
    cols[1].metric("Duplicate", summary["duplicates"])
    cols[2].metric("Failed", summary["failed"])
    cols[3].metric("Skipped", summary["skipped"])
    if summary["errors"]:
        with st.expander("Errors", expanded=True):
            for e in summary["errors"]:
                st.warning(f"{e['file']}: {e['error']}")
    c1, c2 = st.columns([1, 3])
    if c1.button("Review & edit results", type="primary", width="stretch"):
        st.session_state["nav"] = "Review & Edit"
        st.rerun()


def render() -> None:
    theme.header("Process Cards", "Upload one or many visiting-card images and extract fields locally.")

    with st.sidebar:
        st.markdown("### Processing options")
        st.caption("Applied before OCR. Defaults work well for most cards.")
        opts = {
            "upscale": st.checkbox("Upscale small images", value=True),
            "contrast": st.checkbox("Improve contrast (CLAHE)", value=True),
            "sharpen": st.checkbox("Sharpen", value=True),
            "deskew": st.checkbox("Auto-deskew", value=True),
            "denoise": st.checkbox("Denoise (slower)", value=False),
        }
        note = st.text_input("Batch note", value="")

    uploaded = st.file_uploader(
        "Upload visiting cards (JPG, JPEG, PNG)",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
    )

    use_samples = st.checkbox("Use built-in sample cards instead", value=False)

    files = []
    if use_samples:
        files = _sample_files()
        st.info(f"{len(files)} sample card(s) will be processed.")
    elif uploaded:
        st.write(f"{len(uploaded)} file(s) selected")
        cols = st.columns(min(4, len(uploaded)))
        for i, up in enumerate(uploaded):
            with cols[i % len(cols)]:
                st.image(up, caption=up.name, width="stretch")

    ready = bool(files) or bool(uploaded)
    if st.button("Start extraction", type="primary", disabled=not ready):
        if use_samples:
            files = _sample_files()
        else:
            files = []
            prog = st.progress(0.0, text="Saving uploads...")
            for i, up in enumerate(uploaded):
                path = pipeline.save_uploaded_bytes(up.getvalue(), up.name)
                files.append({"name": up.name, "path": path})
                prog.progress((i + 1) / len(uploaded))
            prog.empty()

        batch_id = "batch-" + uuid.uuid4().hex[:12]
        with st.spinner("Loading OCR model (first run downloads weights, later runs are fast)..."):
            pipeline.get_engine().warm_up()
        summary = _run(files, opts, note, batch_id)
        st.divider()
        _show_summary(summary)
