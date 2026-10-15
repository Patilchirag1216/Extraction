"""Excel export with rich, human friendly formatting (openpyxl).

Formatting guarantees
---------------------
* Headers live in the first row, bold, white on a dark background, centred.
* One doctor per horizontal row.
* Text wrapping for headers and long values.
* Column widths and row heights auto-sized (where practical).
* Data cells: TOP vertical + LEFT horizontal alignment.
* Frozen header row + auto filter.
* Thin borders on every used cell.
* When a template is supplied its headers, column order and cell styles are
  preserved and new rows are appended without touching existing data.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .config import FIELD_HEADERS, FIELD_KEYS, HEADER_BY_KEY
from .template_mapping import auto_map, normalise_header

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
HEADER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)
DATA_FONT = Font(size=10)
DATA_ALIGN = Alignment(horizontal="left", vertical="top", wrap_text=True)
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

MIN_WIDTH = 12
MAX_WIDTH = 45
ROW_HEIGHT_BASE = 18


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def read_template_headers(path: str) -> List[str]:
    """Read the header row (first row with content) from an .xlsx template."""
    wb = openpyxl.load_workbook(path, data_only=True)
    try:
        ws = wb.active
        headers: List[str] = []
        for cell in ws[1]:
            value = cell.value
            headers.append(str(value).strip() if value is not None else "")
        # Trim trailing blanks.
        while headers and headers[-1] == "":
            headers.pop()
        return headers
    finally:
        wb.close()


def flatten_record(record: Dict) -> Dict[str, str]:
    """Accept either a database record or an already-flat dict."""
    if "data" in record and isinstance(record.get("data"), dict):
        data = record["data"]
        flat = {k: data.get(k, "") for k in FIELD_KEYS}
        flat["source_file"] = record.get("source_file", "")
        flat["status"] = record.get("status", "")
        return flat
    flat = {k: record.get(k, "") for k in FIELD_KEYS}
    flat["source_file"] = record.get("source_file", "")
    flat["status"] = record.get("status", "")
    return flat


def _column_width(text: str) -> int:
    longest = 0
    for part in str(text).splitlines() or [""]:
        longest = max(longest, len(part))
    return max(MIN_WIDTH, min(MAX_WIDTH, longest + 2))


def _estimate_row_height(values: Sequence[str], widths: Sequence[int]) -> float:
    lines = 1
    for value, width in zip(values, widths):
        text = str(value or "")
        if not text:
            continue
        # raw newlines + wrapping estimate
        per_line = max(1, width - 2)
        needed = len(text) / per_line
        lines = max(lines, int(needed) + text.count("\n") + 1)
    return min(150, max(ROW_HEIGHT_BASE, lines * 14.5))


def _style_header(ws, n_cols: int, header_row: int = 1) -> None:
    for col in range(1, n_cols + 1):
        cell = ws.cell(row=header_row, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGN
        cell.border = BORDER
    ws.row_dimensions[header_row].height = 28


def _apply_data_formatting(ws, n_cols: int, header_row: int = 1) -> None:
    last_row = ws.max_row
    widths = [MIN_WIDTH] * n_cols
    for row in range(header_row + 1, last_row + 1):
        row_values = []
        for col in range(1, n_cols + 1):
            cell = ws.cell(row=row, column=col)
            cell.font = DATA_FONT
            cell.alignment = DATA_ALIGN
            cell.border = BORDER
            value = cell.value
            text = str(value) if value is not None else ""
            row_values.append(text)
            widths[col - 1] = max(widths[col - 1], _column_width(text))
        ws.row_dimensions[row].height = _estimate_row_height(row_values, widths)

    # Header widths should at least fit the header text.
    for col in range(1, n_cols + 1):
        header_text = str(ws.cell(row=header_row, column=col).value or "")
        widths[col - 1] = max(widths[col - 1], _column_width(header_text))

    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width

    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    last_col_letter = get_column_letter(n_cols)
    ws.auto_filter.ref = f"A{header_row}:{last_col_letter}{last_row}"


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def export_records(
    records: Sequence[Dict],
    output_path: str,
    headers: Optional[Sequence[str]] = None,
    mapping: Optional[Dict[str, str]] = None,
    template_path: Optional[str] = None,
    append: bool = False,
    sheet_name: str = "Doctors",
) -> str:
    """Write records to ``output_path`` and return the path.

    * ``template_path`` + ``append=True``  -> append to the uploaded workbook.
    * ``template_path`` + ``append=False`` -> reuse template headers/format,
      replacing previous data rows.
    * no template                          -> new workbook with default headers.
    """
    flat_records = [flatten_record(r) for r in records]

    if template_path:
        wb = openpyxl.load_workbook(template_path)
        ws = wb.active
        if headers is None:
            headers = read_template_headers(template_path)
        if mapping is None:
            mapping = auto_map(list(flat_records[0].keys()) if flat_records else FIELD_KEYS, list(headers))
        write_header = False
        if append:
            start_row = _next_data_row(ws)
        else:
            start_row = 2
            _clear_data_rows(ws)
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name
        if headers is None:
            from .config import EXPORT_FIELD_SCHEMA

            headers = [h for _, h in EXPORT_FIELD_SCHEMA]
        if mapping is None:
            mapping = {k: HEADER_BY_KEY.get(k, "") for k in FIELD_KEYS}
            mapping.update({"source_file": "Source File", "status": "Status"})
        start_row = 2
        write_header = True

    headers = list(headers)
    header_index = {normalise_header(h): idx + 1 for idx, h in enumerate(headers)}
    # Reverse map: header -> field key
    field_for_header: Dict[str, str] = {}
    for field_key, header in (mapping or {}).items():
        if not header:
            continue
        field_for_header.setdefault(header, field_key)

    if write_header:
        for idx, header in enumerate(headers, start=1):
            ws.cell(row=1, column=idx, value=header)

    row = start_row
    for rec in flat_records:
        for col, header in enumerate(headers, start=1):
            field_key = field_for_header.get(header)
            value = rec.get(field_key, "") if field_key else ""
            ws.cell(row=row, column=col, value=value if value != "" else None)
        row += 1

    n_cols = len(headers)
    if write_header:
        _style_header(ws, n_cols, header_row=1)
    _apply_data_formatting(ws, n_cols, header_row=1)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    wb.save(output_path)
    wb.close()
    return output_path


def _next_data_row(ws) -> int:
    """First empty data row (skips any trailing blank rows)."""
    for row in range(2, ws.max_row + 2):
        if all(ws.cell(row=row, column=c).value in (None, "") for c in range(1, ws.max_column + 1)):
            return row
    return ws.max_row + 1


def _clear_data_rows(ws) -> None:
    if ws.max_row >= 2:
        ws.delete_rows(2, ws.max_row - 1)
