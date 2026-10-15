"""Rule / regex / position based information extraction from OCR output.

The extractor never invents values: every field is either taken verbatim from a
recognised text region or left empty.  Each field also receives a confidence
score so uncertain values can be flagged for manual verification.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .config import FIELD_KEYS, VERIFY_THRESHOLD
from .ocr_engine import OCRBox

# ---------------------------------------------------------------------------
# Lexicons
# ---------------------------------------------------------------------------
QUALIFICATION_TOKENS = [
    "mbbs", "md", "ms", "mds", "dnb", "dm", "mch", "bds", "bhms", "bams",
    "bums", "mbchb", "frcs", "mrcp", "mrcs", "phd", "dgo", "dch", "da", "do",
    "dmrd", "dcp", "dpm", "mph", "dph", "dlo", "doms", "fics", "fiap", "mna",
    "diploma", "dnnb", "pgd", "mdca", "ddd", "msc", "bsc", "mha",
]

SPECIALTY_TOKENS = [
    "cardiolog", "dermatolog", "orthoped", "orthopaed", "pediatric", "pediatr",
    "paediatric", "gynecolog", "gynaecolog", "neurolog", "neurosurgeon",
    "nephrolog", "urolog", "gastro", "endocrinolog", "pulmonolog",
    "rheumatolog", "oncolog", "hematolog", "haematolog", "psychiatr",
    "radiolog", "patholog", "anesthes", "anaesthes", "ophthalmolog",
    "otolaryngolog", "physiotherap", "physician", "surgeon", "dentist",
    "dental", "orthodont", "periodont", "endodont", "prosthodont",
    "pedodont", "cardiologist", "ent", "gynecologist", "gynaecologist",
    "diabetolog", "cosmetolog", "tricholog", "immunolog", "neonatolog",
    "intensivist", "general surgeon", "plastic surgeon", "vascular surgeon",
    "family physician", "general physician", "consultant",
]

DESIGNATION_TOKENS = [
    "senior consultant", "consultant", "chief", "director", "head of department",
    "hod", "professor", "asst. professor", "assistant professor",
    "associate professor", "medical officer", "resident", "registrar",
    "fellow", "specialist", "incharge", "officer", "surgeon-in-chief",
]

CLINIC_TOKENS = [
    "hospital", "clinic", "polyclinic", "poly clinic", "medical center",
    "medical centre", "nursing home", "diagnostic", "diagnostics",
    "healthcare", "health care", "health centre", "health center", "medicare",
    "dental studio", "dental care", "eye care", "physiotherapy", "care",
    "medical", "institute", "trust", "multispeciality", "multispecialty",
    "wellness", "remedies", "labs", "laboratory",
]

ADDRESS_TOKENS = [
    "road", "rd", "street", " st ", "nagar", "colony", "sector", "floor",
    "flat", "building", "bldg", "complex", "market", "main", "cross", "lane",
    "layout", "block", "phase", "park", "chowk", "circle", "near", "opp",
    "opposite", "behind", "beside", "plot", "house", "apartment", "tower",
    "plaza", "arcade", "marg", "path", "gali", "bazar", "bazaar", "estate",
    "extension", "east", "west", "north", "south", "street no", "h.o", "po",
    "district", "dist", "taluka", "tq", "post", "village", "ganj", "pura",
    "peth", "wadi", "chsl", "society", "residency", "heights", "enclave",
]

DAY_TOKENS = [
    "mon", "monday", "tue", "tues", "tuesday", "wed", "wednesday", "thu",
    "thur", "thurs", "thursday", "fri", "friday", "sat", "saturday", "sun",
    "sunday", "weekdays", "weekends", "daily", "holiday",
]

HOURS_KEYWORDS = [
    "timing", "timings", "hours", "opd", "consultation hours", "visiting hours",
    "by appointment", "appointment", "availability", "clinic hours",
]

SPECIALTY_EXCLUDE = {"consultant"}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _has_token(text_lower: str, tokens: Sequence[str]) -> Optional[str]:
    for tok in tokens:
        pattern = r"\b" + re.escape(tok.strip()) + r"\b"
        if re.search(pattern, text_lower):
            return tok
    return None


# ---------------------------------------------------------------------------
# Bounding-box grouping into lines
# ---------------------------------------------------------------------------
@dataclass
class Line:
    text: str
    boxes: List[OCRBox] = field(default_factory=list)
    y_center: float = 0.0
    x_min: float = 0.0
    x_max: float = 0.0
    y_min: float = 0.0
    y_max: float = 0.0
    height: float = 0.0
    score: float = 0.0
    cx: float = 0.0

    def finalize(self) -> None:
        self.x_min = min(b.x_min for b in self.boxes)
        self.x_max = max(b.x_max for b in self.boxes)
        self.y_min = min(b.y_min for b in self.boxes)
        self.y_max = max(b.y_max for b in self.boxes)
        self.y_center = (self.y_min + self.y_max) / 2.0
        self.cx = (self.x_min + self.x_max) / 2.0
        self.height = max(b.height for b in self.boxes)
        self.score = sum(b.score for b in self.boxes) / max(1, len(self.boxes))


def build_lines(boxes: Sequence[OCRBox]) -> List[Line]:
    """Group OCR boxes into text lines based on position.

    Boxes are merged into one line when they share a similar vertical centre
    *and* are horizontally close.  The horizontal proximity test prevents text
    from a decorated side-panel being glued to the main body text.
    """
    boxes = list(boxes)
    if not boxes:
        return []
    ordered = sorted(boxes, key=lambda b: (b.cy, b.x_min))
    heights = sorted(b.height for b in boxes)
    median_h = heights[len(heights) // 2] or 10.0
    tol = median_h * 0.6
    gap_tol = median_h * 2.0

    groups: List[Dict] = []
    for b in ordered:
        placed = False
        for g in groups:
            gy = (g["ymin"] + g["ymax"]) / 2.0
            y_ok = abs(b.cy - gy) <= tol
            x_ok = b.x_min <= g["xmax"] + gap_tol and b.x_max >= g["xmin"] - gap_tol
            if y_ok and x_ok:
                g["boxes"].append(b)
                g["ymin"] = min(g["ymin"], b.y_min)
                g["ymax"] = max(g["ymax"], b.y_max)
                g["xmin"] = min(g["xmin"], b.x_min)
                g["xmax"] = max(g["xmax"], b.x_max)
                placed = True
                break
        if not placed:
            groups.append({
                "boxes": [b],
                "ymin": b.y_min, "ymax": b.y_max,
                "xmin": b.x_min, "xmax": b.x_max,
            })

    lines: List[Line] = []
    for g in groups:
        grp_sorted = sorted(g["boxes"], key=lambda b: b.x_min)
        text = _norm(" ".join(b.text for b in grp_sorted))
        ln = Line(text=text, boxes=grp_sorted)
        ln.finalize()
        lines.append(ln)
    lines.sort(key=lambda l: (l.y_center, l.x_min))
    return lines


# ---------------------------------------------------------------------------
# Column / doctor-block detection
# ---------------------------------------------------------------------------
def _coverage_gaps(boxes: Sequence[OCRBox], image_width: int) -> List[Tuple[int, int]]:
    coverage = [0] * (image_width + 1)
    for b in boxes:
        lo = max(0, int(b.x_min))
        hi = min(image_width, int(b.x_max))
        for x in range(lo, hi + 1):
            coverage[x] = 1
    gaps: List[Tuple[int, int]] = []
    start = None
    for x in range(image_width + 1):
        if coverage[x] == 0:
            if start is None:
                start = x
        else:
            if start is not None:
                gaps.append((start, x - 1))
                start = None
    if start is not None:
        gaps.append((start, image_width))
    return gaps


def detect_box_columns(boxes: Sequence[OCRBox], image_width: int) -> List[List[OCRBox]]:
    """Split OCR boxes into two columns when the card clearly has two blocks.

    A split is only accepted for a wide, near-central vertical gap with
    substantial content on both sides.  This avoids mistaking a decorated
    side-panel for a second doctor.
    """
    boxes = list(boxes)
    if len(boxes) < 6:
        return [boxes]
    best = None
    for (a, b) in _coverage_gaps(boxes, image_width):
        width = b - a
        if width < 0.05 * image_width:
            continue
        center = (a + b) / 2.0
        # The gap must be reasonably central.
        if center < 0.30 * image_width or center > 0.70 * image_width:
            continue
        left = [x for x in boxes if x.cx < center]
        right = [x for x in boxes if x.cx >= center]
        if len(left) >= 3 and len(right) >= 3:
            if best is None or width > best[0]:
                best = (width, center)
    if best is None:
        return [boxes]
    split = best[1]
    left = [x for x in boxes if x.cx < split]
    right = [x for x in boxes if x.cx >= split]
    return [left, right]


def detect_columns(lines: Sequence[Line], image_width: int) -> List[List[Line]]:
    """Split lines into columns when the card clearly has two text blocks."""
    if len(lines) < 4:
        return [list(lines)]
    coverage = [0] * (image_width + 1)
    for ln in lines:
        lo = max(0, int(ln.x_min))
        hi = min(image_width, int(ln.x_max))
        for x in range(lo, hi + 1):
            coverage[x] = 1

    # Find zero-coverage gaps.
    gaps: List[Tuple[int, int]] = []
    start = None
    for x in range(image_width + 1):
        if coverage[x] == 0:
            if start is None:
                start = x
        else:
            if start is not None:
                gaps.append((start, x - 1))
                start = None
    if start is not None:
        gaps.append((start, image_width))

    best = None
    for (a, b) in gaps:
        width = b - a
        if width < 0.06 * image_width:
            continue
        center = (a + b) / 2.0
        if center < 0.22 * image_width or center > 0.78 * image_width:
            continue
        # Require content on both sides.
        left = [ln for ln in lines if ln.cx < center]
        right = [ln for ln in lines if ln.cx >= center]
        if len(left) >= 2 and len(right) >= 2:
            if best is None or width > best[0]:
                best = (width, center)
    if best is None:
        return [list(lines)]
    split = best[1]
    left = [ln for ln in lines if ln.cx < split]
    right = [ln for ln in lines if ln.cx >= split]
    return [left, right]


# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
WEBSITE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9\-]{2,})+\.?(?:/[^\s]*)?"
)
TLD_HINT = re.compile(
    r"\.(com|in|org|net|co|io|info|biz|clinic|health|care|hospital|"
    r"hospital|med|edu|gov|site|online|app|drapp|xyz)(/|$|\b)",
    re.IGNORECASE,
)
PHONE_CANDIDATE_RE = re.compile(r"(?<![A-Za-z0-9\-])(?:\+?\d[\d\s\-().]{6,}\d)")
REG_KEYWORD_RE = re.compile(
    r"(reg(?:istration)?\.?\s*(?:no|number|#)?\.?\s*[:\-]?\s*)([A-Za-z0-9\-/ ]{3,})",
    re.IGNORECASE,
)
PIN_RE = re.compile(r"\b(\d{6})\b")
TIME_RE = re.compile(r"\b\d{1,2}[:.\-]\d{2}\b|\b\d{1,2}\s?(?:am|pm|a\.m|p\.m)\b", re.IGNORECASE)
NAME_TITLE_RE = re.compile(r"\b(dr|doctor|prof|professor)\.?\b", re.IGNORECASE)


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def extract_phones(texts: Sequence[str]) -> Tuple[str, str, float]:
    """Return (phone, mobile, confidence).

    ``mobile`` holds a 10-digit Indian mobile number when present; ``phone``
    holds a landline when available and otherwise falls back to the mobile.
    """
    mobiles: List[str] = []
    landlines: List[str] = []
    for raw in texts:
        for m in PHONE_CANDIDATE_RE.finditer(raw):
            candidate = m.group(0)
            d = _digits(candidate)
            if len(d) < 7:
                continue
            if d.startswith("91") and len(d) == 12:
                d = d[2:]
            elif d.startswith("0") and len(d) >= 11:
                d = d.lstrip("0")
            if len(d) == 10 and d[0] in "6789":
                if d not in mobiles:
                    mobiles.append(d)
            elif 8 <= len(d) <= 11:
                if d not in landlines:
                    landlines.append(d)
    mobile = mobiles[0] if mobiles else ""
    if landlines:
        phone = landlines[0]
    else:
        phone = mobile
    conf = 0.9 if (mobiles or landlines) else 0.0
    return phone, mobile, conf


def extract_emails(texts: Sequence[str]) -> Tuple[str, float]:
    for raw in texts:
        m = EMAIL_RE.search(raw)
        if m:
            return m.group(0).lower(), 0.95
    return "", 0.0


def extract_websites(texts: Sequence[str]) -> Tuple[str, float]:
    emails = " ".join(EMAIL_RE.findall(" ".join(texts)))
    for raw in texts:
        for m in WEBSITE_RE.finditer(raw):
            cand = m.group(0).strip()
            if "@" in cand:
                continue
            if cand in emails:
                continue
            # Require a plausible TLD or a www prefix.
            if cand.lower().startswith("www.") or TLD_HINT.search(cand):
                return cand.rstrip(".,;"), 0.85
    return "", 0.0


def extract_registration(texts: Sequence[str]) -> Tuple[str, float]:
    for raw in texts:
        m = REG_KEYWORD_RE.search(raw)
        if m:
            value = _norm(m.group(2)).strip(":- ")
            value = value.split("  ")[0]
            if value:
                return value, 0.8
    return "", 0.0


def _is_qualification(text_lower: str) -> bool:
    return _has_token(text_lower, QUALIFICATION_TOKENS) is not None


def extract_qualification(lines: Sequence[Line]) -> Tuple[str, float]:
    parts = []
    scores = []
    for ln in lines:
        toks = [t for t in QUALIFICATION_TOKENS if re.search(r"\b" + re.escape(t) + r"\b", ln.text.lower())]
        if toks:
            parts.append(ln.text)
            scores.append(ln.score)
    if not parts:
        return "", 0.0
    return " ; ".join(_norm(p) for p in parts), min(0.95, sum(scores) / len(scores) + 0.05)


def extract_specialty(lines: Sequence[Line]) -> Tuple[str, float]:
    primary: List[str] = []
    primary_scores: List[float] = []
    fallback: List[str] = []
    fallback_scores: List[float] = []
    for ln in lines:
        tl = ln.text.lower()
        matched = any(
            re.search(r"\b" + re.escape(tok), tl)
            for tok in SPECIALTY_TOKENS
            if tok not in SPECIALTY_EXCLUDE
        )
        if not matched:
            continue
        # Prefer lines that are not pure qualification strings.
        if _is_qualification(tl):
            fallback.append(ln.text)
            fallback_scores.append(ln.score)
        else:
            primary.append(ln.text)
            primary_scores.append(ln.score)
    if primary:
        return primary[0], min(0.9, sum(primary_scores) / len(primary_scores) + 0.05)
    if fallback:
        return fallback[0], min(0.8, sum(fallback_scores) / len(fallback_scores))
    return "", 0.0


def extract_designation(lines: Sequence[Line]) -> Tuple[str, float]:
    for ln in lines:
        tok = _has_token(ln.text.lower(), DESIGNATION_TOKENS)
        if tok:
            return ln.text, min(0.85, ln.score + 0.05)
    return "", 0.0


def extract_clinic(lines: Sequence[Line], name_line: Optional[Line]) -> Tuple[str, float]:
    for ln in lines:
        if name_line is not None and ln is name_line:
            continue
        if _is_qualification(ln.text.lower()):
            continue
        if NAME_TITLE_RE.search(ln.text) and len(ln.text) < 60:
            # A doctor-name line that only coincidentally contains a clinic word.
            continue
        tok = _has_token(ln.text.lower(), CLINIC_TOKENS)
        if tok:
            return ln.text, min(0.85, ln.score + 0.02)
    return "", 0.0


def _is_address_line(text: str) -> bool:
    tl = text.lower()
    if EMAIL_RE.search(text) or PHONE_CANDIDATE_RE.search(text):
        return False
    if _has_token(tl, ADDRESS_TOKENS):
        return True
    if PIN_RE.search(" " + text.split(",")[-1] + " ") and "," in text:
        return True
    if re.search(r"\b\d{6}\b", text) and "," in text:
        return True
    return False


def extract_address(lines: Sequence[Line], used: Sequence[int]) -> Tuple[str, float]:
    parts: List[str] = []
    scores: List[float] = []
    for ln in lines:
        if id(ln) in used:
            continue
        if _is_address_line(ln.text):
            parts.append(ln.text)
            scores.append(ln.score)
    if not parts:
        return "", 0.0
    return ", ".join(_norm(p).strip(" ,") for p in parts), min(0.75, sum(scores) / len(scores))


def extract_hours(lines: Sequence[Line]) -> Tuple[str, float]:
    for ln in lines:
        tl = ln.text.lower()
        if _has_token(tl, HOURS_KEYWORDS):
            return ln.text, min(0.9, ln.score + 0.05)
        if TIME_RE.search(ln.text) and (_has_token(tl, DAY_TOKENS) or "am" in tl or "pm" in tl):
            return ln.text, min(0.85, ln.score + 0.05)
    return "", 0.0


def _clean_name(text: str) -> str:
    m = NAME_TITLE_RE.search(text)
    if not m:
        return ""
    seg = text[m.start():]
    # Stop at a comma or a qualification token.
    seg = seg.split(",")[0]
    for tok in QUALIFICATION_TOKENS + ["consultant", "specialist"]:
        cut = re.search(r"\b" + re.escape(tok) + r"\b", seg, re.IGNORECASE)
        if cut and cut.start() > 3:
            seg = seg[: cut.start()]
    seg = _norm(seg).strip(" -,.")
    # Normalise a bare "Dr" to "Dr."
    seg = re.sub(r"^(dr|doctor|prof|professor)\s", lambda mm: _title(mm.group(1)), seg,
                 count=1, flags=re.IGNORECASE)
    return seg


def _title(word: str) -> str:
    w = word.lower()
    if w in ("dr", "doctor"):
        return "Dr. "
    if w in ("prof", "professor"):
        return "Prof. "
    return word.title() + " "


def _name_ok(cleaned: str) -> bool:
    stripped = NAME_TITLE_RE.sub("", cleaned)
    letters = re.sub(r"[^A-Za-z]", "", stripped)
    return len(letters) >= 2


def detect_name_lines(lines: Sequence[Line]) -> List[Line]:
    return [
        ln for ln in lines
        if NAME_TITLE_RE.search(ln.text) and _name_ok(_clean_name(ln.text))
    ]


def guess_name_without_title(lines: Sequence[Line], used_ids: set, image_height: int) -> Tuple[str, float]:
    """Best-effort name guess when the card has no explicit Dr./Prof. prefix."""
    candidates = [
        ln for ln in lines
        if id(ln) not in used_ids
        and ln.y_center < image_height * 0.7
        and not _is_address_line(ln.text)
        and not EMAIL_RE.search(ln.text)
        and 2 <= len(ln.text.split()) <= 5
        and not _is_qualification(ln.text.lower())
    ]
    if not candidates:
        return "", 0.0
    # Prefer the largest font, then the earliest line.
    best = max(candidates, key=lambda l: (round(l.height, 1), -l.y_center))
    if not re.match(r"^[A-Z][A-Za-z.\- ]+$", best.text.strip()):
        return "", 0.0
    # Low confidence: this is a guess and must be verified.
    return best.text.strip(), 0.45


# ---------------------------------------------------------------------------
# Per-block extraction
# ---------------------------------------------------------------------------
def extract_from_lines(lines: Sequence[Line], image_size: Tuple[int, int]) -> Dict:
    """Extract a single doctor record from a set of lines."""
    image_w, image_h = image_size
    texts = [ln.text for ln in lines]
    used_ids: set = set()

    name_lines = detect_name_lines(lines)
    doctor_name = ""
    name_conf = 0.0
    name_line: Optional[Line] = None
    if name_lines:
        primary = max(name_lines, key=lambda l: l.height)
        doctor_name = _clean_name(primary.text)
        name_conf = min(0.95, primary.score + 0.05)
        name_line = primary
        used_ids.add(id(primary))

    qualification, qual_conf = extract_qualification(lines)
    specialty, spec_conf = extract_specialty(lines)
    designation, desig_conf = extract_designation(lines)
    clinic, clinic_conf = extract_clinic(lines, name_line)
    hours, hours_conf = extract_hours(lines)
    reg_no, reg_conf = extract_registration(texts)
    # Remove the registration value so its digits are not mistaken for a phone.
    phone_texts = texts
    if reg_no:
        phone_texts = [t.replace(reg_no, " ") for t in texts]
    phone, mobile, phone_conf = extract_phones(phone_texts)
    email, email_conf = extract_emails(texts)
    website, web_conf = extract_websites(texts)

    used_for_address = set()
    for ln in lines:
        tl = ln.text.lower()
        if (
            _is_qualification(tl)
            or _has_token(tl, SPECIALTY_TOKENS)
            or _has_token(tl, DESIGNATION_TOKENS)
            or _has_token(tl, CLINIC_TOKENS)
            or _has_token(tl, HOURS_KEYWORDS)
            or EMAIL_RE.search(ln.text)
            or PHONE_CANDIDATE_RE.search(ln.text)
        ):
            used_for_address.add(id(ln))
    if name_line is not None:
        used_for_address.add(id(name_line))
    address, addr_conf = extract_address(lines, used_for_address)

    if not doctor_name:
        doctor_name, name_conf = guess_name_without_title(lines, used_ids, image_h)

    record = {
        "doctor_name": doctor_name,
        "qualification": qualification,
        "specialty": specialty,
        "designation": designation,
        "clinic_name": clinic,
        "address": address,
        "phone": phone,
        "mobile": mobile,
        "email": email,
        "website": website,
        "registration_no": reg_no,
        "visiting_hours": hours,
    }
    confidence = {
        "doctor_name": name_conf,
        "qualification": qual_conf,
        "specialty": spec_conf,
        "designation": desig_conf,
        "clinic_name": clinic_conf,
        "address": addr_conf,
        "phone": phone_conf,
        "mobile": phone_conf if mobile else 0.0,
        "email": email_conf,
        "website": web_conf,
        "registration_no": reg_conf,
        "visiting_hours": hours_conf,
    }
    return {"fields": record, "confidence": confidence}


def _segment_by_name(lines: Sequence[Line]) -> List[List[Line]]:
    """Split lines into doctor blocks.

    Handles both vertically stacked doctors and side-by-side doctors
    (where name lines sit at a similar vertical level but different x).
    """
    name_lines = detect_name_lines(lines)
    if len(name_lines) < 2:
        return [list(lines)]
    if len(name_lines) == 2:
        n1, n2 = name_lines[0], name_lines[1]
        ydiff = abs(n1.y_center - n2.y_center)
        # If names are at very similar vertical level but horizontally apart,
        # treat as side-by-side columns and assign each line to nearest name by x.
        if ydiff < 30 and abs(n1.cx - n2.cx) > 200:
            blocks = [[] for _ in name_lines]
            for ln in lines:
                d0 = abs(ln.cx - n1.cx) + 0.5 * abs(ln.y_center - n1.y_center)
                d1 = abs(ln.cx - n2.cx) + 0.5 * abs(ln.y_center - n2.y_center)
                idx = 0 if d0 <= d1 else 1
                blocks[idx].append(ln)
            return [b for b in blocks if b]
    name_lines = sorted(name_lines, key=lambda l: l.y_center)
    boundaries = [l.y_center for l in name_lines]
    blocks: List[List[Line]] = [[] for _ in boundaries]
    for ln in lines:
        idx = 0
        for i, b in enumerate(boundaries):
            if ln.y_center >= b - 5:
                idx = i
        blocks[idx].append(ln)
    return [b for b in blocks if b]


def extract_records(boxes: Sequence[OCRBox], image_size: Tuple[int, int]) -> List[Dict]:
    """Return one or more doctor records found on the card."""
    boxes = list(boxes)
    if not boxes:
        return []
    image_w, _ = image_size
    box_columns = detect_box_columns(boxes, image_w)
    records: List[Dict] = []
    if len(box_columns) >= 2:
        for col_boxes in box_columns:
            lines = build_lines(col_boxes)
            if not lines:
                continue
            for block in _segment_by_name(lines):
                records.append(extract_from_lines(block, image_size))
    else:
        lines = build_lines(boxes)
        if not lines:
            return []
        for block in _segment_by_name(lines):
            records.append(extract_from_lines(block, image_size))
    return records
