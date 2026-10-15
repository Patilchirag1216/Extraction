"""Map canonical extraction fields onto arbitrary Excel column headers.

Users can upload their own workbook; we read the header row and match each
canonical field to the most likely column.  The UI lets the user override the
automatic suggestion.
"""
from __future__ import annotations

import re
from typing import Dict, List, Sequence

# Generic words that must never, on their own, justify a match (e.g. "S.No").
STOPWORDS = {
    "no", "number", "num", "id", "the", "of", "and", "sr", "s", "sl", "serial",
    "a", "an", "for", "to", "#", "details", "detail", "info",
}

# Headers that are clearly just row numbers / serial columns.
SERIAL_HEADERS = {
    "s no", "sr no", "sl no", "serial no", "serial number", "no", "sno",
    "srno", "s l no", "s n", "index", "row no",
}

SYNONYMS: Dict[str, List[str]] = {
    "doctor_name": ["doctor name", "name", "doctor", "dr name", "physician",
                    "physician name", "consultant name", "full name"],
    "qualification": ["qualification", "qualifications", "degree", "degrees",
                      "education", "qual", "academic"],
    "specialty": ["specialty", "speciality", "specialization", "specialisation",
                  "department", "dept", "field", "expertise"],
    "designation": ["designation", "designation/role", "role", "position",
                    "title", "post"],
    "clinic_name": ["clinic", "clinic name", "hospital", "hospital name",
                    "clinic / hospital", "clinic/hospital", "organisation",
                    "organization", "institute", "establishment"],
    "address": ["address", "clinic address", "location", "full address",
                "postal address"],
    "phone": ["phone", "phone no", "phone number", "telephone", "tel",
              "landline", "contact", "contact no", "contact number"],
    "mobile": ["mobile", "mobile no", "mobile number", "cell", "cell no",
               "whatsapp", "cellphone"],
    "email": ["email", "email id", "e-mail", "mail", "mail id", "email address"],
    "website": ["website", "web", "url", "site", "web site", "web address"],
    "registration_no": ["registration no", "registration number", "reg no",
                        "reg. no", "regno", "registration", "reg number",
                        "license no", "licence no", "mci no"],
    "visiting_hours": ["visiting hours", "visiting time", "timings", "timing",
                       "hours", "opd timings", "consultation hours",
                       "availability", "schedule"],
    "source_file": ["source file", "source", "file", "image", "file name"],
    "status": ["status", "verification", "verified"],
}


def normalise_header(header: str) -> str:
    h = (header or "").strip().lower()
    h = h.replace("&", "and")
    h = re.sub(r"[\.\(\)\[\]/\\,_\-]+", " ", h)
    h = re.sub(r"\s+", " ", h).strip()
    return h


def _score_field(field_key: str, header_norm: str) -> int:
    if not header_norm:
        return 0
    if header_norm in SERIAL_HEADERS:
        return 0
    best = 0
    for syn in SYNONYMS.get(field_key, []):
        syn_n = normalise_header(syn)
        if syn_n == header_norm:
            best = max(best, 100)
        elif syn_n in header_norm or header_norm in syn_n:
            if syn_n not in STOPWORDS:
                best = max(best, 70)
        else:
            syn_tokens = set(syn_n.split()) - STOPWORDS
            hdr_tokens = set(header_norm.split()) - STOPWORDS
            common = syn_tokens & hdr_tokens
            if common:
                best = max(best, 45 + 15 * len(common))
    return best


def auto_map(field_keys: Sequence[str], headers: Sequence[str]) -> Dict[str, str]:
    """Return {field_key: header} using best-effort scoring, 1:1 where possible."""
    norm_headers = [normalise_header(h) for h in headers]
    candidates = []
    for fk in field_keys:
        for idx, hn in enumerate(norm_headers):
            score = _score_field(fk, hn)
            if score > 0:
                candidates.append((score, fk, idx))
    candidates.sort(reverse=True)

    mapping: Dict[str, str] = {}
    used_headers = set()
    for score, fk, idx in candidates:
        if fk in mapping or idx in used_headers:
            continue
        mapping[fk] = headers[idx]
        used_headers.add(idx)

    for fk in field_keys:
        mapping.setdefault(fk, "")
    return mapping
