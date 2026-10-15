# Doctor Visiting Card Extraction

A fully **offline** web application that reads doctor visiting cards (JPG / JPEG / PNG),
extracts structured information with local OCR, lets a human verify and correct every
field, and exports clean, formatted Excel files.

Nothing is sent to the cloud. **No API keys. No paid AI services.** All OCR and
extraction runs on your own machine with [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
and OpenCV.

---

## Features

- **Modern Streamlit dashboard** that runs locally at `http://localhost:8501`.
- **Batch upload** of many cards at once with a live progress bar and per-file error handling.
- **Local OCR** via PaddleOCR (detection + recognition models downloaded once, then cached).
- **Rule / regex / position based extraction** of:
  doctor name, qualification, specialty, designation, clinic/hospital, address,
  phone, mobile, email, website, registration number and visiting hours.
- **Multiple doctors per card** – side-by-side and stacked layouts are split into
  separate records using OCR bounding-box geometry.
- **No invented data** – missing fields stay empty, and low-confidence fields are
  flagged for manual verification with a confidence bar.
- **Side-by-side review** of the original card image and editable extracted fields,
  with an optional overlay showing the detected text regions.
- **Duplicate detection** across the whole history (matched on name / phone / email).
- **Excel template mapping** – upload your own workbook and map extracted fields to
  its real column headers (with automatic suggestions).
- **Append or create** – add rows to an existing workbook without deleting previous
  records, or generate a fresh file.
- **Formatted Excel output** – bold contrasting headers, wrapped text, auto column
  widths, top/left data alignment, frozen header row, filters and borders.
- **SQLite history** of every batch with **resume** support for interrupted runs.

---

## Requirements

- **Windows 10/11 (64-bit)**
- **Python 3.10 – 3.12** installed.
  > PaddlePaddle does **not** publish wheels for Python 3.13 / 3.14 yet, so the app
  > will not run on those versions. Python **3.12** is recommended and is what this
  > project was built and tested with.
- Internet access **only for the first-time installation** (downloading packages and
  OCR models). After that everything runs offline.

---

## Installation (Windows)

### 1. Get the code

Place the project folder anywhere, e.g. `C:\Users\<you>\Desktop\vcard`.

### 2. Make sure Python 3.12 is available

Check what you have:

```powershell
py -0p
```

If 3.12 is missing, install it:

```powershell
winget install --id Python.Python.3.12 -e
```

### 3. Run the setup script (easiest)

From the project folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

This creates a `.venv` virtual environment and installs everything in
`requirements.txt`.

### 3b. Or install manually

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python -m pip install -r requirements.txt
```

> The install downloads several hundred MB (PaddlePaddle, PaddleX, Streamlit, OpenCV).
> This is a one-time step.

---

## Running the app

Double-click **`run_app.bat`**, or run:

```powershell
.\.venv\Scripts\python -m streamlit run app.py
```

Then open the URL Streamlit prints (default **http://localhost:8501**).

On the **first** extraction the OCR models are downloaded automatically
(a few tens of MB) and cached in `%USERPROFILE%\.paddlex\official_models`.
Subsequent runs start instantly and work offline.

---

## How to use

1. **Process Cards**
   - Upload one or more `.jpg` / `.jpeg` / `.png` files (or tick *Use built-in sample
     cards* to try it out).
   - Adjust the optional preprocessing toggles if a card is small, low-contrast or tilted.
   - Click **Start extraction**. Watch the progress bar; results are saved to SQLite.
2. **Review & Edit**
   - Pick a batch/record. The original card is shown on the left, editable fields on the right.
   - Focus on fields flagged with a ⚠ / low confidence bar.
   - Toggle *Show detected text regions* to see what OCR found.
   - Use **Save changes** or **Save & verify**.
3. **Export to Excel**
   - Choose a batch (or *All batches*), optionally filter to verified / non-duplicate rows.
   - Use the default columns, **or** upload your own `.xlsx` template and map fields to
     its actual headers.
   - Optionally *append* to that workbook instead of creating a new file.
   - Click **Generate Excel file** and download it.
4. **History & Resume**
   - See every batch, its status and counts. Resume an interrupted batch or delete one.

---

## Project structure

```
vcard/
├── app.py                      # Streamlit entry point (navigation + layout)
├── run_app.bat                 # One-click launcher (Windows)
├── setup.ps1                   # Creates .venv and installs dependencies
├── requirements.txt
├── README.md
├── ui/                         # Browser interface (Streamlit)
│   ├── theme.py                # Global CSS / layout helpers
│   ├── common.py               # Shared widgets & helpers
│   ├── page_dashboard.py
│   ├── page_process.py         # Upload + batch processing + progress
│   ├── page_review.py          # Original image beside editable fields
│   ├── page_export.py          # Template mapping + Excel export
│   └── page_history.py         # History + resume
├── vcard/                      # Core processing package
│   ├── config.py               # Paths, field schema, thresholds
│   ├── preprocessing.py        # OpenCV loading, deskew, contrast, resize
│   ├── ocr_engine.py           # PaddleOCR wrapper (lazy, cached)
│   ├── extraction.py           # Rules / regex / position based extraction
│   ├── validation.py           # Field validation, confidence, duplicate keys
│   ├── template_mapping.py     # Map fields -> arbitrary Excel headers
│   ├── excel_export.py         # openpyxl export + formatting
│   ├── database.py             # SQLite: batches, records, resume
│   ├── pipeline.py             # Orchestrates image -> records -> DB
│   └── visualize.py            # Draw OCR boxes for review
├── scripts/
│   ├── generate_samples.py     # Creates synthetic test cards
│   ├── smoke_test.py           # Backend end-to-end test
│   ├── test_app.py             # Renders every page (Streamlit AppTest)
│   └── test_ui_workflow.py     # Full UI workflow test
├── data/
│   ├── samples/                # Built-in sample cards
│   ├── uploads/                # Saved uploads
│   └── vcard.db                # SQLite database (created automatically)
├── templates/                  # Uploaded / sample Excel templates
└── exports/                    # Generated Excel files
```

---

## Excel output

- Headers live in the **first row**, are **bold**, white on a dark blue background and
  **centered**.
- Each doctor is one **horizontal row**; columns are never transposed.
- Headers and long values use **text wrapping**.
- **Column widths** and **row heights** are auto-sized (within sensible limits).
- Data cells use **top + left** alignment.
- The **header row is frozen** and **column filters** are enabled.
- Thin, consistent **borders** on every used cell.
- When you supply a template, its **headers, column order and formatting are preserved**,
  and *append* mode adds new rows without touching existing ones.

`templates/sample_template.xlsx` is provided to demonstrate a custom column layout.

---

## Testing

With the virtual environment active:

```powershell
# Backend end-to-end (OCR -> extract -> validate -> DB -> Excel)
.\.venv\Scripts\python scripts\smoke_test.py

# Regenerate the synthetic sample cards
.\.venv\Scripts\python scripts\generate_samples.py

# Render every Streamlit page and check for errors
.\.venv\Scripts\python scripts\test_app.py

# Full UI workflow (process samples -> review -> export)
.\.venv\Scripts\python scripts\test_ui_workflow.py
```

---

## Notes & troubleshooting

- **`ConvertPirAttribute2RuntimeAttribute not support` on startup / first OCR**
  This is a known PaddlePaddle 3.x CPU bug in the MKLDNN run mode. The application
  disables MKLDNN by default (env flags are set automatically in `app.py` and
  `vcard/ocr_engine.py`), so you should not normally see it. If you do, make sure you
  launch the app with the provided launcher (which keeps those flags) and clear any
  stale model cache in `%USERPROFILE%\.paddlex\official_models`.
- **`No matching distribution found for paddlepaddle`**
  You are on Python 3.13/3.14. Create the environment with Python 3.12
  (`py -3.12 -m venv .venv`).
- **First extraction feels slow**
  The OCR models load/download on first use. Later runs are fast.
- **OCR accuracy**
  Accuracy depends on image quality. The preprocessing toggles and the manual review
  step exist precisely to handle hard cards. The extractor never invents data — verify
  anything flagged.

---

## Privacy

All image processing and text extraction happen locally. The app makes no outbound
network calls at runtime, requires no API keys, and stores everything (images, records,
history) on your disk under `data/` and `exports/`.
