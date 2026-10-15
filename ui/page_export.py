"""Export page: Excel output with optional template mapping and append."""
from __future__ import annotations

import hashlib
import os
from datetime import datetime

import pandas as pd
import streamlit as st

from vcard import config, database, excel_export, template_mapping
from vcard.config import FIELD_LABELS

from . import theme
from .common import batch_options

DEFAULT_MODE = "Default columns"
TEMPLATE_MODE = "Upload Excel template"


def _filtered_records(batch_id):
    if batch_id == "__all__":
        records = database.get_all_records()
    else:
        records = database.get_records(batch_id)
    return records


def render() -> None:
    theme.header("Export to Excel", "Map extracted fields onto your own workbook and download.")

    options = batch_options()
    all_label = "All batches"
    choices = [all_label] + list(options.keys())
    sel = st.selectbox("Source", choices)
    batch_id = "__all__" if sel == all_label else options[sel]

    records = _filtered_records(batch_id)
    if not records:
        st.info("No records to export for this selection.")
        return

    c1, c2 = st.columns(2)
    with c1:
        only_verified = st.checkbox("Only verified records", value=False)
    with c2:
        exclude_dupes = st.checkbox("Exclude possible duplicates", value=True)

    filtered = records
    if only_verified:
        filtered = [r for r in filtered if r.get("verified")]
    if exclude_dupes:
        filtered = [r for r in filtered if not r.get("duplicate_of")]

    st.caption(f"{len(filtered)} of {len(records)} record(s) selected for export.")
    if not filtered:
        st.warning("No records match the current filters.")
        return

    mode = st.radio("Columns", [DEFAULT_MODE, TEMPLATE_MODE], horizontal=True)

    headers = None
    mapping = None
    template_path = None
    append = False

    if mode == DEFAULT_MODE:
        from vcard.config import EXPORT_FIELD_SCHEMA

        headers = [h for _, h in EXPORT_FIELD_SCHEMA]
        st.markdown("**Columns:** " + " | ".join(headers))
    else:
        up = st.file_uploader("Upload Excel template (.xlsx)", type=["xlsx"])
        if up is not None:
            digest = hashlib.md5(up.getvalue()).hexdigest()[:10]
            template_path = os.path.join(config.TEMPLATE_DIR, f"tpl_{digest}.xlsx")
            with open(template_path, "wb") as fh:
                fh.write(up.getvalue())
            headers = excel_export.read_template_headers(template_path)
            st.success(f"Template loaded with {len(headers)} column(s). Map fields below.")
            st.markdown("**Template headers:** " + " | ".join(headers))

            from vcard.config import EXPORT_FIELD_SCHEMA

            field_keys = [k for k, _ in EXPORT_FIELD_SCHEMA]
            auto = template_mapping.auto_map(field_keys, headers)
            mapping = {}
            st.markdown("##### Field mapping")
            cols = st.columns(2)
            skip = "-- skip --"
            for i, key in enumerate(field_keys):
                target = cols[i % 2].selectbox(
                    FIELD_LABELS.get(key, key),
                    [skip] + list(headers),
                    index=([skip] + list(headers)).index(auto.get(key) or skip),
                    key=f"map_{digest}_{key}",
                )
                mapping[key] = "" if target == skip else target
            append = st.checkbox(
                "Append to this workbook (keep existing rows and formatting)",
                value=False,
            )
        else:
            st.info("Upload an .xlsx file to map its columns. Until then default columns are used.")
            template_path = None

    # Preview
    st.markdown("##### Preview")
    preview_rows = []
    for r in filtered[:8]:
        flat = excel_export.flatten_record(r)
        preview_rows.append({FIELD_LABELS[k]: flat.get(k, "") for k in FIELD_LABELS})
    st.dataframe(pd.DataFrame(preview_rows), width="stretch", hide_index=True)

    if st.button("Generate Excel file", type="primary"):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_name = f"doctors_export_{ts}.xlsx"
        out_path = os.path.join(config.EXPORT_DIR, out_name)
        path = excel_export.export_records(
            filtered,
            out_path,
            headers=headers if mode == TEMPLATE_MODE else None,
            mapping=mapping,
            template_path=template_path,
            append=append,
        )
        with open(path, "rb") as fh:
            data = fh.read()
        st.success(f"Created {out_name} ({len(filtered)} row(s)).")
        st.download_button(
            "Download Excel",
            data=data,
            file_name=out_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
