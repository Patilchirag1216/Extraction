"""Central configuration: paths, field schema, OCR settings and thresholds."""
from __future__ import annotations

import os
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(PACKAGE_DIR)

DATA_DIR = os.path.join(APP_ROOT, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
SAMPLE_DIR = os.path.join(DATA_DIR, "samples")
DB_PATH = os.path.join(DATA_DIR, "vcard.db")

EXPORT_DIR = os.path.join(APP_ROOT, "exports")
TEMPLATE_DIR = os.path.join(APP_ROOT, "templates")

for _d in (DATA_DIR, UPLOAD_DIR, SAMPLE_DIR, EXPORT_DIR, TEMPLATE_DIR):
    os.makedirs(_d, exist_ok=True)

# ---------------------------------------------------------------------------
# Supported uploads
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_MIME = ["image/jpeg", "image/png", "image/jpg"]

# ---------------------------------------------------------------------------
# Canonical field schema
# ---------------------------------------------------------------------------
# (key, default header).  The key is the internal name used everywhere in the
# code base and stored in the database.  The header is what appears in a new
# Excel workbook when the user does not provide a template.
FIELD_SCHEMA: List[Tuple[str, str]] = [
    ("doctor_name", "Doctor Name"),
    ("qualification", "Qualification"),
    ("specialty", "Specialty"),
    ("designation", "Designation"),
    ("clinic_name", "Clinic / Hospital"),
    ("address", "Address"),
    ("phone", "Phone"),
    ("mobile", "Mobile"),
    ("email", "Email"),
    ("website", "Website"),
    ("registration_no", "Registration No."),
    ("visiting_hours", "Visiting Hours"),
]

FIELD_KEYS: List[str] = [k for k, _ in FIELD_SCHEMA]
FIELD_HEADERS: List[str] = [h for _, h in FIELD_SCHEMA]
HEADER_BY_KEY = dict(FIELD_SCHEMA)

# Extra, non-extracted columns that can optionally be exported.
META_SCHEMA: List[Tuple[str, str]] = [
    ("source_file", "Source File"),
    ("status", "Status"),
]
META_KEYS = [k for k, _ in META_SCHEMA]
META_HEADERS = [h for _, h in META_SCHEMA]

EXPORT_FIELD_SCHEMA = FIELD_SCHEMA + META_SCHEMA

# Human friendly labels used in the review form.
FIELD_LABELS = {
    "doctor_name": "Doctor Name",
    "qualification": "Qualification",
    "specialty": "Specialty",
    "designation": "Designation",
    "clinic_name": "Clinic / Hospital",
    "address": "Address",
    "phone": "Phone",
    "mobile": "Mobile",
    "email": "Email",
    "website": "Website",
    "registration_no": "Registration No.",
    "visiting_hours": "Visiting Hours",
    "source_file": "Source File",
    "status": "Status",
}

# ---------------------------------------------------------------------------
# Record status values
# ---------------------------------------------------------------------------
STATUS_VERIFIED = "Verified"
STATUS_NEEDS_REVIEW = "Needs Verification"
STATUS_DUPLICATE = "Possible Duplicate"
STATUS_PENDING = "Pending"

# ---------------------------------------------------------------------------
# Thresholds / OCR settings
# ---------------------------------------------------------------------------
# Fields whose extracted confidence is below this value are flagged for the
# user to verify manually.
VERIFY_THRESHOLD = 0.70

OCR_LANG = "en"

# Preprocessing defaults.
PREPROC_UPSCALE_MIN_WIDTH = 1000
PREPROC_UPSCALE_MAX_FACTOR = 3.0

OTSU_SCALE = 1.0

# PaddleOCR flags required for a stable CPU run on Windows (see README).
# Kept here so the whole app can import them consistently.
PADDLE_ENV_DEFAULTS = {
    "PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT": "0",
    "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": "True",
}
