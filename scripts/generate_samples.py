"""Generate synthetic doctor visiting-card images for local testing.

These images are drawn with Pillow only (no external assets) so the whole
pipeline can be exercised end to end without any real patient data.
"""
from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(os.path.dirname(HERE), "data", "samples")

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
]


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = FONT_CANDIDATES
    if bold:
        candidates = [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf"] + FONT_CANDIDATES
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _card(width=1013, height=638, bg="white"):
    img = Image.new("RGB", (width, height), bg)
    return img, ImageDraw.Draw(img)


def sample_1_single(path):
    img, d = _card()
    d.rectangle([0, 0, 1013, 638], outline=(30, 90, 160), width=6)
    d.rectangle([0, 0, 1013, 120], fill=(30, 90, 160))
    title = _font(46, True)
    sub = _font(24)
    d.text((350, 30), "Dr. Ananya Sharma", font=title, fill="white")
    d.text((360, 86), "MBBS, MD (Cardiology)", font=sub, fill=(230, 240, 255))
    body = _font(24)
    small = _font(21)
    y = 160
    d.text((60, y), "Consultant Cardiologist", font=_font(28, True), fill=(20, 20, 20))
    y += 50
    d.text((60, y), "Heart Care Clinic", font=body, fill=(20, 20, 20)); y += 34
    d.text((60, y), "12 MG Road, Sector 5, Pune - 411001", font=small, fill=(40, 40, 40)); y += 30
    d.text((60, y), "Phone: +91 98765 43210, 020 2456 7890", font=small, fill=(40, 40, 40)); y += 30
    d.text((60, y), "Email: ananya.sharma@heartcare.in", font=small, fill=(40, 40, 40)); y += 30
    d.text((60, y), "www.heartcareclinic.in", font=small, fill=(40, 40, 40)); y += 30
    d.text((60, y), "Reg. No: MMC-2010-45821", font=small, fill=(40, 40, 40)); y += 30
    d.text((60, y), "Mon-Sat: 10:00 AM - 2:00 PM, 5:00 PM - 8:00 PM", font=small, fill=(40, 40, 40))
    img.save(path)


def sample_2_two_doctors(path):
    img, d = _card(1200, 640)
    d.rectangle([0, 0, 1200, 640], outline=(120, 30, 120), width=6)
    d.rectangle([590, 40, 610, 600], fill=(220, 200, 220))
    head = _font(38, True)
    body = _font(22)
    small = _font(19)
    # left doctor
    x = 40
    d.text((x, 40), "Dr. Rakesh Verma", font=head, fill=(80, 10, 80))
    d.text((x, 90), "MBBS, MS (Orthopaedics)", font=body, fill=(40, 40, 40))
    y = 130
    for line in [
        "Orthopaedic Surgeon",
        "Verma Bone & Joint Clinic",
        "45 Ring Road, Nashik - 422001",
        "Mobile: 9123456780",
        "rakesh.verma@bones.in",
        "Reg No: NMC-2012-99871",
        "Mon-Fri: 9:30 AM - 1:00 PM",
    ]:
        d.text((x, y), line, font=small, fill=(40, 40, 40)); y += 32
    # right doctor
    x = 640
    d.text((x, 40), "Dr. Meera Iyer", font=head, fill=(80, 10, 80))
    d.text((x, 90), "MBBS, DNB (Paediatrics)", font=body, fill=(40, 40, 40))
    y = 130
    for line in [
        "Paediatrician",
        "Little Steps Child Care",
        "88 Station Road, Thane - 400601",
        "Phone: 9988776655",
        "meera.iyer@littlesteps.com",
        "Website: www.littlesteps.com",
        "Tue-Sun: 11:00 AM - 3:00 PM",
    ]:
        d.text((x, y), line, font=small, fill=(40, 40, 40)); y += 32
    img.save(path)


def sample_3_dentist(path):
    img, d = _card(1013, 638, "white")
    d.rectangle([0, 0, 1013, 638], outline=(10, 130, 120), width=6)
    d.rectangle([0, 0, 300, 638], fill=(10, 130, 120))
    head = _font(42, True)
    body = _font(23)
    small = _font(20)
    d.text((20, 120), "Dr.", font=_font(34, True), fill="white")
    d.text((20, 165), "Karan", font=_font(34, True), fill="white")
    d.text((20, 210), "Mehta", font=_font(34, True), fill="white")
    x = 340
    d.text((x, 60), "Dr. Karan Mehta", font=head, fill=(10, 90, 85))
    d.text((x, 118), "BDS, MDS (Orthodontics)", font=body, fill=(40, 40, 40))
    y = 170
    for line in [
        "Dental Surgeon & Orthodontist",
        "Smile Dental Studio",
        "3rd Floor, City Centre, Camp Road, Nagpur 440001",
        "Mobile: 9822011223",
        "smile.dental@yahoo.in",
        "Reg. No: DCI-2015-33210",
        "Hours: Mon to Sat 10 AM - 7 PM",
    ]:
        d.text((x, y), line, font=small, fill=(40, 40, 40)); y += 34
    img.save(path)


def sample_4_missing(path):
    """Sparse card: missing several fields (tests no-invention + verification)."""
    img, d = _card(1013, 638, "white")
    head = _font(40, True)
    body = _font(24)
    d.text((80, 120), "Dr. S. Nair", font=head, fill=(0, 0, 0))
    d.text((80, 185), "General Physician", font=body, fill=(30, 30, 30))
    d.text((80, 235), "City Medical Centre", font=body, fill=(30, 30, 30))
    d.text((80, 285), "Phone: 9447788990", font=body, fill=(30, 30, 30))
    img.save(path)


def main():
    os.makedirs(SAMPLES_DIR, exist_ok=True)
    samples = {
        "card1_single.png": sample_1_single,
        "card2_two_doctors.png": sample_2_two_doctors,
        "card3_dentist.png": sample_3_dentist,
        "card4_missing.png": sample_4_missing,
    }
    for name, fn in samples.items():
        path = os.path.join(SAMPLES_DIR, name)
        fn(path)
        print("wrote", path)


if __name__ == "__main__":
    main()
