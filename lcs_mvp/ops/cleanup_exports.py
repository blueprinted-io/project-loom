"""Retention cleanup for export artifacts.

Deletes files from lcs_mvp/data/exports/ and removes corresponding rows from export_artifacts
when they exceed their retention window.

This is intended to be:
- portable (repo-contained)
- safe (won't delete outside EXPORTS_DIR)
- usable from:
  - OS scheduler (systemd timer / cron)
  - manual runs during migration

Run:
  cd lcs_mvp
  source .venv/bin/activate
  python3 -m ops.cleanup_exports --db data/lcs_demo.db

Exit codes:
  0 success
  2 DB missing
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _parse_iso(s: str) -> datetime | None:
    s = (s or "").strip()
    if not s:
        return None
    # sqlite stores ISO like 2026-02-08T14:06:00+00:00; tolerate Z
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class Result:
    scanned: int = 0
    expired: int = 0
    deleted_files: int = 0
    missing_files: int = 0
    db_rows_deleted: int = 0


def cleanup(db_path: Path, exports_dir: Path, now: datetime | None = None) -> Result:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    res = Result()

    rows = conn.execute(
        "SELECT id, path, exported_at, retention_days FROM export_artifacts ORDER BY exported_at ASC"
    ).fetchall()

    for r in rows:
        res.scanned += 1

        exported_at = _parse_iso(str(r["exported_at"] or ""))
        retention_days = int(r["retention_days"])

        if not exported_at:
            # If we can't parse the timestamp, skip.
            continue

        cutoff = exported_at + timedelta(days=retention_days)
        if now <= cutoff:
            continue

        res.expired += 1

        p = Path(str(r["path"] or ""))
        # Safety: only delete within exports_dir
        try:
            p_abs = p.resolve()
            exp_abs = exports_dir.resolve()
            if exp_abs not in p_abs.parents and p_abs != exp_abs:
                # Don't delete outside exports dir.
                continue
        except Exception:
            continue

        if p.exists():
            try:
                p.unlink()
                res.deleted_files += 1
            except Exception:
                # If we fail to delete, keep DB row.
                continue
        else:
            res.missing_files += 1

        conn.execute("DELETE FROM export_artifacts WHERE id=?", (str(r["id"]),))
        res.db_rows_deleted += 1

    conn.commit()
    conn.close()
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/lcs_demo.db")
    ap.add_argument("--exports-dir", default="data/exports")
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(2)

    exports_dir = Path(args.exports_dir)
    exports_dir.mkdir(parents=True, exist_ok=True)

    res = cleanup(db_path=db_path, exports_dir=exports_dir)
    print(res)


if __name__ == "__main__":
    main()
