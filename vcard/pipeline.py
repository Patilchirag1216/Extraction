"""End-to-end processing pipeline: image -> records -> database."""
from __future__ import annotations

import hashlib
import os
from datetime import datetime
from typing import Callable, Dict, List, Optional, Sequence

from . import config, database, extraction, preprocessing, validation, visualize
from .ocr_engine import OCREngine, get_engine

DEFAULT_OPTIONS = {
    "upscale": True,
    "denoise": False,
    "contrast": True,
    "sharpen": True,
    "deskew": True,
}

ProgressCallback = Callable[[int, int, str, str], None]


def file_hash_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def file_hash(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def save_uploaded_bytes(data: bytes, filename: str) -> str:
    """Persist uploaded bytes under data/uploads/<date>/ and return the path."""
    day = datetime.now().strftime("%Y%m%d")
    folder = os.path.join(config.UPLOAD_DIR, day)
    os.makedirs(folder, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in filename)
    path = os.path.join(folder, safe)
    # Avoid overwriting an existing file with the same name.
    base, ext = os.path.splitext(path)
    counter = 1
    while os.path.exists(path):
        path = f"{base}_{counter}{ext}"
        counter += 1
    with open(path, "wb") as fh:
        fh.write(data)
    return path


def process_image(
    image_path: str,
    options: Optional[Dict] = None,
    engine: Optional[OCREngine] = None,
) -> Dict:
    """Run the full extraction on a single image.

    Returns a dict with keys: records, boxes, image (processed BGR), lines.
    """
    opts = {**DEFAULT_OPTIONS, **(options or {})}
    engine = engine or get_engine()

    image = preprocessing.load_image(image_path)
    processed = preprocessing.preprocess(
        image,
        upscale=opts["upscale"],
        denoise=opts["denoise"],
        contrast=opts["contrast"],
        sharpen=opts["sharpen"],
        deskew=opts["deskew"],
    )
    boxes = engine.detect(processed)
    raw_records = extraction.extract_records(boxes, (processed.shape[1], processed.shape[0]))

    finalized: List[Dict] = []
    for raw in raw_records:
        finalized.append(validation.finalize(raw["fields"], raw["confidence"]))

    return {
        "records": finalized,
        "boxes": boxes,
        "image": processed,
        "raw": raw_records,
    }


def process_batch(
    files: Sequence[Dict],
    batch_id: str,
    options: Optional[Dict] = None,
    resume: bool = False,
    progress: Optional[ProgressCallback] = None,
    note: str = "",
    collect_overlays: bool = False,
) -> Dict:
    """Process a set of uploaded files and persist the results.

    ``files`` is a sequence of ``{"name": str, "path": str}`` dicts.
    Returns a summary dict with counts and the list of stored record ids.
    """
    opts = {**DEFAULT_OPTIONS, **(options or {})}
    engine = get_engine()

    existing = database.get_batch(batch_id)
    if existing is None:
        database.create_batch(
            batch_id, note=note, total=len(files), options=opts
        )

    done_hashes = database.processed_hashes(batch_id) if resume else set()

    total = len(files)
    processed = 0
    failed = 0
    skipped = 0
    duplicates = 0
    record_ids: List[int] = []
    errors: List[Dict] = []
    overlays: Dict[str, bytes] = {}

    for index, item in enumerate(files, start=1):
        name = item["name"]
        path = item["path"]
        try:
            fh = file_hash(path)
            if resume and fh in done_hashes:
                skipped += 1
                if progress:
                    progress(index, total, name, "skipped")
                continue

            result = process_image(path, opts, engine)
            records = result["records"]
            if collect_overlays:
                overlay = visualize.draw_boxes(result["image"], result["boxes"])
                overlays[name] = preprocessing.encode_png(
                    preprocessing.downscale_for_preview(overlay)
                )
            if not records:
                failed += 1
                errors.append({"file": name, "error": "No text detected"})
                if progress:
                    progress(index, total, name, "failed")
                continue

            for rec_index, rec in enumerate(records):
                dkey = validation.duplicate_key(rec["fields"])
                dup = database.find_duplicate(dkey)
                duplicate_of = None
                status = rec["status"]
                if dup is not None:
                    duplicate_of = dup["id"]
                    status = config.STATUS_DUPLICATE
                    duplicates += 1
                rid = database.save_record(
                    batch_id=batch_id,
                    source_file=name,
                    image_path=path,
                    source_hash=fh,
                    record_index=rec_index,
                    data=rec["fields"],
                    confidence=rec["confidence"],
                    needs_verification=rec["needs_verification"],
                    missing=rec["missing"],
                    status=status,
                    dup_key=dkey,
                    duplicate_of=duplicate_of,
                )
                record_ids.append(rid)
            processed += 1
            database.update_batch(batch_id, processed=processed + skipped, failed=failed)
            if progress:
                progress(index, total, name, "ok")
        except Exception as exc:  # keep going on individual failures
            failed += 1
            errors.append({"file": name, "error": str(exc)})
            if progress:
                progress(index, total, name, "failed")

    final_status = "completed" if failed == 0 else "completed_with_errors"
    database.update_batch(
        batch_id,
        processed=processed + skipped,
        failed=failed,
        status=final_status,
    )
    return {
        "batch_id": batch_id,
        "total": total,
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
        "duplicates": duplicates,
        "record_ids": record_ids,
        "errors": errors,
        "overlays": overlays,
    }
