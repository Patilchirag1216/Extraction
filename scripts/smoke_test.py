"""End-to-end smoke test: OCR -> extract -> validate -> DB -> Excel."""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vcard import config, database, excel_export, pipeline  # noqa: E402

# Use an isolated database so repeated runs are not seen as duplicates.
_TMP_DB = os.path.join(tempfile.gettempdir(), "vcard_smoke.db")
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
config.DB_PATH = _TMP_DB

SAMPLES = ["card1_single.png", "card2_two_doctors.png", "card3_dentist.png", "card4_missing.png"]


def main():
    database.init_db()
    batch_id = "smoke-" + str(os.getpid())
    files = [
        {"name": s, "path": os.path.join(config.SAMPLE_DIR, s)} for s in SAMPLES
    ]

    def progress(i, n, name, status):
        print(f"  [{i}/{n}] {name}: {status}")

    summary = pipeline.process_batch(files, batch_id, progress=progress, note="smoke test")
    print("\nSUMMARY:", summary)

    records = database.get_records(batch_id)
    print(f"\nStored {len(records)} records:")
    for r in records:
        d = r["data"]
        print("-" * 70)
        print(f"file={r['source_file']} idx={r['record_index']} status={r['status']}")
        for k in ("doctor_name", "qualification", "specialty", "designation",
                  "clinic_name", "address", "phone", "mobile", "email", "website",
                  "registration_no", "visiting_hours"):
            conf = r["confidence"].get(k, 0)
            flag = " !" if k in r["needs_verification"] else ""
            if d.get(k):
                print(f"    {k:16s}: {d.get(k)}   (conf {conf:.2f}){flag}")
        if r["missing"]:
            print(f"    missing: {', '.join(r['missing'])}")

    out = os.path.join(config.EXPORT_DIR, "smoke_export.xlsx")
    excel_export.export_records(records, out, append=False)
    print(f"\nExported -> {out}")

    # Duplicate detection: re-run the same batch against the DB.
    summary2 = pipeline.process_batch(files, "smoke-dup-" + str(os.getpid()),
                                      note="dup test")
    print("\nDUP SUMMARY:", {k: summary2[k] for k in ("processed", "duplicates")})
    print("STATS:", database.stats())


if __name__ == "__main__":
    main()
