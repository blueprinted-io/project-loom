from __future__ import annotations

import sqlite3
from typing import Any

from .database import db, utc_now_iso
from .utils import _json_load


# ---------------------------------------------------------------------------
# Versioned-table registry
# ---------------------------------------------------------------------------

_VERSIONED_TABLES = frozenset({"tasks", "workflows", "assessment_items"})


# ---------------------------------------------------------------------------
# Audit log writer
# ---------------------------------------------------------------------------

def audit(
    entity_type: str,
    record_id: str,
    version: int,
    action: str,
    actor: str,
    note: str | None = None,
    *,
    conn: sqlite3.Connection | None = None,
) -> None:
    """Write an audit_log row.

    Important: if you're already inside `with db() as conn:` and have performed writes,
    pass that same `conn=` here. Otherwise audit() will open a second connection and
    SQLite can throw `OperationalError: database is locked`.
    """
    if conn is None:
        with db() as conn2:
            conn2.execute(
                "INSERT INTO audit_log(entity_type, record_id, version, action, actor, at, note) VALUES (?,?,?,?,?,?,?)",
                (entity_type, record_id, version, action, actor, utc_now_iso(), note),
            )
        return

    conn.execute(
        "INSERT INTO audit_log(entity_type, record_id, version, action, actor, at, note) VALUES (?,?,?,?,?,?,?)",
        (entity_type, record_id, version, action, actor, utc_now_iso(), note),
    )


# ---------------------------------------------------------------------------
# Helpers used by audit / review flows
# ---------------------------------------------------------------------------

def _normalize_domains(json_str: str | None) -> list[str]:
    """Parse a JSON domain array, normalising each entry to lowercase stripped strings."""
    return [v for x in (_json_load(json_str) or []) if (v := str(x).strip().lower())]


def _fetch_return_note(conn: sqlite3.Connection, entity_type: str, record_id: str, version: int) -> dict[str, Any] | None:
    """Return the most recent return-for-changes note for an entity, or None."""
    rn = conn.execute(
        "SELECT note, at, actor FROM audit_log"
        " WHERE entity_type=? AND record_id=? AND version=? AND action='return_for_changes'"
        " ORDER BY at DESC LIMIT 1",
        (entity_type, record_id, version),
    ).fetchone()
    if rn and rn["note"]:
        return {"note": rn["note"], "at": rn["at"], "actor": rn["actor"]}
    return None


def get_latest_version(conn: sqlite3.Connection, table: str, record_id: str) -> int | None:
    if table not in _VERSIONED_TABLES:
        raise ValueError(f"get_latest_version: unknown table {table!r}")
    row = conn.execute(
        f"SELECT MAX(version) AS v FROM {table} WHERE record_id=?", (record_id,)
    ).fetchone()
    return int(row["v"]) if row and row["v"] is not None else None
