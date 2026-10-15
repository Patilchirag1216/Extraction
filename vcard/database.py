"""SQLite persistence: batches, records, history and resume support."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import config

_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS batches (
    id               TEXT PRIMARY KEY,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    note             TEXT NOT NULL DEFAULT '',
    status           TEXT NOT NULL DEFAULT 'processing',
    total            INTEGER NOT NULL DEFAULT 0,
    processed        INTEGER NOT NULL DEFAULT 0,
    failed           INTEGER NOT NULL DEFAULT 0,
    template_headers TEXT NOT NULL DEFAULT '[]',
    options          TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS records (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id           TEXT NOT NULL,
    source_file        TEXT NOT NULL,
    image_path         TEXT,
    source_hash        TEXT NOT NULL DEFAULT '',
    record_index       INTEGER NOT NULL DEFAULT 0,
    data               TEXT NOT NULL,
    confidence         TEXT NOT NULL DEFAULT '{}',
    needs_verification TEXT NOT NULL DEFAULT '[]',
    missing            TEXT NOT NULL DEFAULT '[]',
    status             TEXT NOT NULL DEFAULT 'Pending',
    verified           INTEGER NOT NULL DEFAULT 0,
    dup_key            TEXT NOT NULL DEFAULT '',
    duplicate_of       INTEGER,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_records_batch ON records(batch_id);
CREATE INDEX IF NOT EXISTS idx_records_dupkey ON records(dup_key);
CREATE INDEX IF NOT EXISTS idx_records_hash ON records(source_hash);
"""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def get_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or config.DB_PATH
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    with _LOCK:
        conn = get_conn(db_path)
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Batches
# ---------------------------------------------------------------------------
def create_batch(
    batch_id: str,
    note: str = "",
    total: int = 0,
    options: Optional[Dict] = None,
    template_headers: Optional[List[str]] = None,
    db_path: Optional[str] = None,
) -> None:
    now = _now()
    with _LOCK:
        conn = get_conn(db_path)
        try:
            conn.execute(
                "INSERT INTO batches (id, created_at, updated_at, note, status, "
                "total, processed, failed, template_headers, options) "
                "VALUES (?, ?, ?, ?, 'processing', ?, 0, 0, ?, ?)",
                (
                    batch_id, now, now, note, total,
                    json.dumps(template_headers or []),
                    json.dumps(options or {}),
                ),
            )
            conn.commit()
        finally:
            conn.close()


def update_batch(batch_id: str, db_path: Optional[str] = None, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = _now()
    cols = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [batch_id]
    with _LOCK:
        conn = get_conn(db_path)
        try:
            conn.execute(f"UPDATE batches SET {cols} WHERE id=?", values)
            conn.commit()
        finally:
            conn.close()


def get_batch(batch_id: str, db_path: Optional[str] = None) -> Optional[Dict]:
    conn = get_conn(db_path)
    try:
        row = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_batches(db_path: Optional[str] = None) -> List[Dict]:
    conn = get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM batches ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_batch(batch_id: str, db_path: Optional[str] = None) -> None:
    with _LOCK:
        conn = get_conn(db_path)
        try:
            conn.execute("DELETE FROM records WHERE batch_id=?", (batch_id,))
            conn.execute("DELETE FROM batches WHERE id=?", (batch_id,))
            conn.commit()
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------
def save_record(
    batch_id: str,
    source_file: str,
    image_path: str,
    source_hash: str,
    record_index: int,
    data: Dict,
    confidence: Dict,
    needs_verification: List[str],
    missing: List[str],
    status: str,
    dup_key: str = "",
    duplicate_of: Optional[int] = None,
    verified: int = 0,
    db_path: Optional[str] = None,
) -> int:
    now = _now()
    with _LOCK:
        conn = get_conn(db_path)
        try:
            cur = conn.execute(
                "INSERT INTO records (batch_id, source_file, image_path, source_hash,"
                " record_index, data, confidence, needs_verification, missing, status,"
                " verified, dup_key, duplicate_of, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    batch_id, source_file, image_path, source_hash, record_index,
                    json.dumps(data), json.dumps(confidence),
                    json.dumps(needs_verification), json.dumps(missing),
                    status, verified, dup_key, duplicate_of, now, now,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()


def get_records(batch_id: str, db_path: Optional[str] = None) -> List[Dict]:
    conn = get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM records WHERE batch_id=? ORDER BY source_file, record_index",
            (batch_id,),
        ).fetchall()
        return [_row_to_record(r) for r in rows]
    finally:
        conn.close()


def get_record(record_id: int, db_path: Optional[str] = None) -> Optional[Dict]:
    conn = get_conn(db_path)
    try:
        row = conn.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone()
        return _row_to_record(row) if row else None
    finally:
        conn.close()


def get_all_records(db_path: Optional[str] = None) -> List[Dict]:
    conn = get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM records ORDER BY batch_id, source_file, record_index"
        ).fetchall()
        return [_row_to_record(r) for r in rows]
    finally:
        conn.close()


def update_record(
    record_id: int,
    data: Optional[Dict] = None,
    confidence: Optional[Dict] = None,
    needs_verification: Optional[List[str]] = None,
    missing: Optional[List[str]] = None,
    status: Optional[str] = None,
    verified: Optional[int] = None,
    dup_key: Optional[str] = None,
    db_path: Optional[str] = None,
) -> None:
    fields: Dict[str, Any] = {"updated_at": _now()}
    if data is not None:
        fields["data"] = json.dumps(data)
    if confidence is not None:
        fields["confidence"] = json.dumps(confidence)
    if needs_verification is not None:
        fields["needs_verification"] = json.dumps(needs_verification)
    if missing is not None:
        fields["missing"] = json.dumps(missing)
    if status is not None:
        fields["status"] = status
    if verified is not None:
        fields["verified"] = verified
    if dup_key is not None:
        fields["dup_key"] = dup_key
    cols = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [record_id]
    with _LOCK:
        conn = get_conn(db_path)
        try:
            conn.execute(f"UPDATE records SET {cols} WHERE id=?", values)
            conn.commit()
        finally:
            conn.close()


def processed_hashes(batch_id: str, db_path: Optional[str] = None) -> set:
    """Source hashes already stored for a batch (used to resume)."""
    conn = get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT source_hash FROM records WHERE batch_id=?",
            (batch_id,),
        ).fetchall()
        return {r["source_hash"] for r in rows if r["source_hash"]}
    finally:
        conn.close()


def find_duplicate(dup_key: str, exclude_id: Optional[int] = None,
                   db_path: Optional[str] = None) -> Optional[Dict]:
    if not dup_key:
        return None
    conn = get_conn(db_path)
    try:
        sql = "SELECT * FROM records WHERE dup_key=? AND dup_key<>''"
        params: List[Any] = [dup_key]
        if exclude_id is not None:
            sql += " AND id<>?"
            params.append(exclude_id)
        sql += " ORDER BY id LIMIT 1"
        row = conn.execute(sql, params).fetchone()
        return _row_to_record(row) if row else None
    finally:
        conn.close()


def stats(db_path: Optional[str] = None) -> Dict:
    conn = get_conn(db_path)
    try:
        total_batches = conn.execute("SELECT COUNT(*) c FROM batches").fetchone()["c"]
        total_records = conn.execute("SELECT COUNT(*) c FROM records").fetchone()["c"]
        verified = conn.execute(
            "SELECT COUNT(*) c FROM records WHERE verified=1"
        ).fetchone()["c"]
        review = conn.execute(
            "SELECT COUNT(*) c FROM records WHERE status='Needs Verification'"
        ).fetchone()["c"]
        dupes = conn.execute(
            "SELECT COUNT(*) c FROM records WHERE duplicate_of IS NOT NULL"
        ).fetchone()["c"]
        processing = conn.execute(
            "SELECT COUNT(*) c FROM batches WHERE status='processing'"
        ).fetchone()["c"]
        return {
            "total_batches": total_batches,
            "total_records": total_records,
            "verified": verified,
            "needs_review": review,
            "duplicates": dupes,
            "processing_batches": processing,
        }
    finally:
        conn.close()


def _row_to_record(row: sqlite3.Row) -> Dict:
    d = dict(row)
    for key in ("data", "confidence", "needs_verification", "missing"):
        raw = d.get(key)
        try:
            d[key] = json.loads(raw) if raw else ([] if key != "data" else {})
        except (TypeError, json.JSONDecodeError):
            d[key] = [] if key != "data" else {}
    return d
