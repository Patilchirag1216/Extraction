"""Review & edit page: original image beside editable extracted fields."""
from __future__ import annotations

import streamlit as st

from vcard import config, database, validation
from vcard.config import FIELD_KEYS, FIELD_LABELS

from . import theme
from .common import batch_options, confidence_html, load_rgb, record_label, status_badge

AREA_FIELDS = {"address", "visiting_hours"}


def _save_record(rec, mark_verified: bool):
    fields = {}
    for key in FIELD_KEYS:
        widget_key = f"{rec['id']}__{key}"
        fields[key] = (st.session_state.get(widget_key) or "").strip()

    confidence = dict(rec["confidence"])
    original = rec["data"]
    for key in FIELD_KEYS:
        if (fields.get(key) or "") != (original.get(key) or ""):
            # A value the human typed or confirmed is fully trusted.
            confidence[key] = 1.0

    result = validation.finalize(fields, confidence)
    status = result["status"]
    verified = rec["verified"]
    if mark_verified:
        status = config.STATUS_VERIFIED
        verified = 1
        result["needs_verification"] = []
    elif rec.get("duplicate_of") and status == config.STATUS_VERIFIED:
        status = config.STATUS_NEEDS_REVIEW

    database.update_record(
        rec["id"],
        data=result["fields"],
        confidence=result["confidence"],
        needs_verification=result["needs_verification"],
        missing=result["missing"],
        status=status,
        verified=verified,
        dup_key=validation.duplicate_key(result["fields"]),
    )
    st.toast("Saved", icon="✅")


def render() -> None:
    theme.header("Review & Edit", "Check every field against the original card before exporting.")

    options = batch_options()
    if not options:
        st.info("No batches available yet. Process some cards first.")
        if st.button("Go to Process Cards"):
            st.session_state["nav"] = "Process Cards"
            st.rerun()
        return

    # Default to the most recent batch.
    default_id = st.session_state.get("last_batch_id")
    labels = list(options.keys())
    default_index = 0
    if default_id and default_id in options.values():
        default_index = list(options.values()).index(default_id)

    with st.sidebar:
        st.markdown("### Review")
        label = st.selectbox("Batch", labels, index=default_index)
        batch_id = options[label]
        show_overlay = st.toggle("Show detected text regions", value=False)
        verified_only = st.checkbox("Jump to unverified only", value=False)

    records = database.get_records(batch_id)
    if not records:
        st.warning("This batch has no stored records.")
        return

    verified_n = sum(1 for r in records if r.get("verified"))
    st.caption(f"{verified_n} of {len(records)} record(s) marked verified.")

    labels_map = {record_label(r, i): r for i, r in enumerate(records, start=1)}
    keys = list(labels_map.keys())
    if verified_only:
        keys = [k for k, r in labels_map.items() if not r.get("verified")] or keys

    sel_key = "review_record"
    if st.session_state.get(sel_key) not in keys:
        st.session_state[sel_key] = keys[0]
    sel = st.selectbox("Record", keys, key=sel_key)
    rec = labels_map[sel]
    idx = list(labels_map.keys()).index(sel)

    left, right = st.columns([1, 1], gap="large")

    with left:
        st.markdown("#### Original card")
        img = None
        overlays = st.session_state.get("overlays", {})
        if show_overlay and rec["source_file"] in overlays:
            st.image(overlays[rec["source_file"]], width="stretch")
            st.caption("Overlay: green = detected text regions.")
        else:
            img = load_rgb(rec["image_path"])
            if img is not None:
                st.image(img, width="stretch")
            else:
                st.warning("Original image not found on disk.")
        st.markdown(
            f"**Source:** {rec['source_file']} &nbsp;&nbsp; "
            f"{theme.badge(rec['status'], status_badge(rec['status']))}",
            unsafe_allow_html=True,
        )
        if rec.get("duplicate_of"):
            st.warning(
                f"Possible duplicate of record #{rec['duplicate_of']} "
                "(matched on name / phone / email)."
            )
            if st.button("Not a duplicate", key=f"notdup_{rec['id']}"):
                database.update_record(
                    rec["id"], status=config.STATUS_NEEDS_REVIEW, dup_key=""
                )
                st.rerun()
        if rec["missing"]:
            st.caption("Missing on card: " + ", ".join(FIELD_LABELS.get(k, k) for k in rec["missing"]))

    with right:
        st.markdown("#### Extracted fields")
        st.caption("Edit any value. Fields below the confidence bar are flagged for verification.")
        for key in FIELD_KEYS:
            conf = rec["confidence"].get(key, 0.0)
            needs = key in rec["needs_verification"]
            label = FIELD_LABELS[key]
            widget_key = f"{rec['id']}__{key}"
            value = rec["data"].get(key, "")
            if key in AREA_FIELDS:
                st.text_area(label, value=value, key=widget_key, height=70)
            else:
                st.text_input(label, value=value, key=widget_key)
            st.markdown(confidence_html(conf, needs), unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        if c1.button("Save changes", width="stretch"):
            _save_record(rec, mark_verified=False)
            st.rerun()
        if c2.button("Save & verify", type="primary", width="stretch"):
            _save_record(rec, mark_verified=True)
            st.rerun()
        if c3.button("Next record", width="stretch"):
            nxt = keys[(idx + 1) % len(keys)]
            st.session_state[sel_key] = nxt
            st.rerun()
