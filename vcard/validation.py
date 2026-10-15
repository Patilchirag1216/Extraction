"""Field validation, confidence finalisation and duplicate keying."""
from __future__ import annotations

import re
from typing import Dict, List

from .config import (
    FIELD_KEYS,
    STATUS_NEEDS_REVIEW,
    STATUS_VERIFIED,
    VERIFY_THRESHOLD,
)

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?\d[\d\s\-()]{6,}$")
WEBSITE_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+(?:/[^\s]*)?$",
    re.IGNORECASE,
)


def validate_email(value: str) -> bool:
    return bool(value) and bool(EMAIL_RE.match(value.strip()))


def validate_phone(value: str) -> bool:
    if not value:
        return False
    digits = re.sub(r"\D", "", value)
    return 7 <= len(digits) <= 13


def validate_website(value: str) -> bool:
    if not value:
        return False
    return bool(WEBSITE_RE.match(value.strip()))


def validate_registration(value: str) -> bool:
    if not value:
        return False
    return len(re.sub(r"\s", "", value)) >= 3


VALIDATORS = {
    "email": validate_email,
    "phone": validate_phone,
    "mobile": validate_phone,
    "website": validate_website,
    "registration_no": validate_registration,
}


def normalise_record(fields: Dict[str, str]) -> Dict[str, str]:
    out = {k: (v or "").strip() for k, v in fields.items()}
    for k in FIELD_KEYS:
        out.setdefault(k, "")
    if out.get("email"):
        out["email"] = out["email"].lower()
    if out.get("phone"):
        out["phone"] = re.sub(r"\s+", " ", out["phone"]).strip()
    return out


def finalize(
    fields: Dict[str, str],
    confidence: Dict[str, float],
    threshold: float = VERIFY_THRESHOLD,
) -> Dict:
    """Validate fields and compute verification flags.

    Returns a dict with: fields, confidence, needs_verification, missing,
    status, valid (bool per validated field).
    """
    fields = normalise_record(fields)
    conf = {k: float(confidence.get(k, 0.0)) for k in FIELD_KEYS}
    valid: Dict[str, bool] = {}

    for key, validator in VALIDATORS.items():
        value = fields.get(key, "")
        if not value:
            valid[key] = False
            continue
        ok = validator(value)
        valid[key] = ok
        if not ok:
            # An invalid pattern means we are unsure -> lower confidence.
            conf[key] = min(conf.get(key, 0.0), 0.4)

    needs_verification: List[str] = []
    missing: List[str] = []
    for key in FIELD_KEYS:
        value = fields.get(key, "")
        if not value:
            missing.append(key)
            continue
        if conf.get(key, 0.0) < threshold:
            needs_verification.append(key)

    # An empty name is a hard problem: always needs attention.
    if not fields.get("doctor_name"):
        needs_verification.append("doctor_name")

    status = STATUS_VERIFIED if not needs_verification else STATUS_NEEDS_REVIEW
    return {
        "fields": fields,
        "confidence": conf,
        "valid": valid,
        "needs_verification": sorted(set(needs_verification)),
        "missing": missing,
        "status": status,
    }


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def duplicate_key(fields: Dict[str, str]) -> str:
    """Build a normalised key used to detect duplicate records."""
    name = re.sub(r"[^a-z]", "", (fields.get("doctor_name") or "").lower())
    name = re.sub(r"^(dr|doctor|prof|professor)", "", name)
    contact = _digits(fields.get("mobile") or fields.get("phone") or "")
    email = (fields.get("email") or "").lower()
    return "|".join(x for x in (name, contact, email) if x)
