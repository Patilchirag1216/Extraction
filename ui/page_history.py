"""History page: browse batches, resume interrupted runs, delete."""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from vcard import database, pipeline

from . import theme
from .common import status_badge


def _resume(batch):
    try:
        options = json.loads(batch.get("options") or "{}")
    except json.JSONDecodeError:
        options = {}
    files = options.get("files")
    preproc = options.get("preproc", {})
    if not files:
        st.error("This batch did not record its input files, so it cannot be resumed.")
        return
    bar = st.progress(0.0, text="Resuming...")

    def progress(i, n, name, state):
        bar.progress(i / max(1, n), text=f"[{i}/{n}] {name}: {state}")

    summary = pipeline.process_batch(
        files, batch["id"], options=preproc, resume=True, progress=progress
    )
    bar.progress(1.0, text="Done")
    st.success(
        f"Resumed: {summary['processed']} processed, {summary['skipped']} skipped "
        f"(already done), {summary['failed']} failed."
    )
    st.rerun()


def render() -> None:
    theme.header("History & Resume", "Every batch is stored in SQLite; interrupted runs can continue.")

    batches = database.list_batches()
    if not batches:
        st.info("No batches recorded yet.")
        return

    rows = [
        {
            "Batch": b["id"],
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

    labels = {f"{b['created_at'][:19]} | {b['note'] or 'batch'} | {b['id']}": b for b in batches}
    sel = st.selectbox("Select a batch", list(labels.keys()))
    batch = labels[sel]

    records = database.get_records(batch["id"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Records", len(records))
    c2.metric("Verified", sum(1 for r in records if r.get("verified")))
    c3.metric("Duplicates", sum(1 for r in records if r.get("duplicate_of")))
    c4.metric("Status", batch["status"])

    col = st.columns(4)
    if col[0].button("Open in Review", width="stretch"):
        st.session_state["last_batch_id"] = batch["id"]
        st.session_state["nav"] = "Review & Edit"
        st.rerun()
    can_resume = batch["status"] in ("processing", "completed_with_errors")
    if col[1].button("Resume batch", disabled=not can_resume, width="stretch"):
        _resume(batch)
    if col[2].button("Delete batch", width="stretch"):
        database.delete_batch(batch["id"])
        st.toast("Batch deleted")
        st.rerun()

    if records:
        st.markdown("##### Records")
        data = [
            {
                "File": r["source_file"],
                "Doctor": r["data"].get("doctor_name", ""),
                "Phone": r["data"].get("mobile") or r["data"].get("phone", ""),
                "Email": r["data"].get("email", ""),
                "Status": r["status"],
            }
            for r in records
        ]
        st.dataframe(pd.DataFrame(data), width="stretch", hide_index=True)
