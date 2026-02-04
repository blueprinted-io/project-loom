"""Backfill optional step.actions into existing SQLite task records.

This is a lightweight migration for the MVP.

Rules:
- step.text and step.completion remain canonical and required.
- step.actions is optional and represents "how" (tool/environment specific).
- We only add actions when we can derive something concrete from the step text.

Run:
  cd lcs_mvp
  source .venv/bin/activate
  python3 seed/backfill_step_actions.py --db data/lcs_demo.db

Or backfill both known DBs:
  python3 seed/backfill_step_actions.py --both
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from typing import Any


def _json_load(s: str | None) -> Any:
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def _json_dump(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False)


_CMD_RE = re.compile(r"`([^`]+)`")
_EDIT_PATH_RE = re.compile(r"\b(edit|open)\s+(/[^\s]+)", re.IGNORECASE)
_FILE_PATH_RE = re.compile(r"(/etc/[^\s]+|/var/[^\s]+|/usr/[^\s]+|/opt/[^\s]+|/home/[^\s]+)")


def derive_actions(step_text: str) -> list[str]:
    """Derive a small set of optional actions.

    Aggressive (MVP-friendly): always return at least 1-2 helpful action lines for non-empty steps.
    Prefer concrete CLI/file actions when possible; fall back to generic-but-executable guidance.
    """
    s = (step_text or "").strip()
    if not s:
        return []

    actions: list[str] = []

    low = s.lower()

    # 1) Explicit commands in backticks
    cmds = [c.strip() for c in _CMD_RE.findall(s) if c.strip()]
    for c in cmds[:3]:
        actions.append(c)

    # 2) File path editing/opening
    m = _EDIT_PATH_RE.search(s)
    if m:
        path = m.group(2)
        actions.append(f"sudo nano {path}  # or your editor of choice")
    else:
        pm = _FILE_PATH_RE.search(s)
        if pm:
            path = pm.group(1)
            actions.append(f"sudo nano {path}  # or your editor of choice")

    # 3) Debian-biased verb-driven defaults
    if re.search(r"\b(restart|reload)\b", low) and not any("systemctl" in a for a in actions):
        actions.append("sudo systemctl restart <service>")
        actions.append("sudo systemctl status <service> --no-pager")

    if re.search(r"\b(enable)\b", low) and not any("systemctl" in a for a in actions):
        actions.append("sudo systemctl enable --now <service>")
        actions.append("systemctl is-enabled <service> && systemctl is-active <service>")

    if re.search(r"\b(disable)\b", low) and not any("systemctl" in a for a in actions):
        actions.append("sudo systemctl disable --now <service>")
        actions.append("systemctl is-enabled <service> || true")

    if re.search(r"\b(install)\b", low) and not any("apt-get" in a for a in actions):
        actions.append("sudo apt-get update")
        actions.append("sudo apt-get install -y <package>")
        actions.append("dpkg -l | grep -i <package> || true")

    if re.search(r"\b(update|upgrade)\b", low) and not any("apt-get" in a for a in actions):
        actions.append("sudo apt-get update")
        actions.append("sudo apt-get upgrade -y")

    if re.search(r"\b(create|add)\b", low) and re.search(r"\b(user|account)\b", low) and not any("adduser" in a for a in actions):
        actions.append("sudo adduser <username>")
        actions.append("id <username> || getent passwd <username>")

    if re.search(r"\b(group)\b", low) and re.search(r"\b(add|grant)\b", low) and not any("usermod" in a for a in actions):
        actions.append("sudo usermod -aG <group> <username>")
        actions.append("id <username>")

    if re.search(r"\b(log|journal)\b", low) and not any("journalctl" in a for a in actions):
        actions.append("sudo journalctl -u <service> -n 200 --no-pager")

    if re.search(r"\b(mount|fstab)\b", low):
        actions.append("sudo cp -a /etc/fstab /etc/fstab.bak")
        actions.append("sudo nano /etc/fstab")
        actions.append("sudo mount -a")
        actions.append("findmnt --verify || true")

    # NOTE: do not add generic "evidence capture" boilerplate here.
    # Confirmation belongs in step.completion (human observation), not in actions.

    # 4) If still empty, leave actions empty. Some steps are self-explanatory.
    if not actions:
        return []

    # De-dupe preserving order
    out: list[str] = []
    seen: set[str] = set()
    for a in actions:
        x = a.strip()
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)

    return out


def normalize_steps(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        return []

    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            out.append({"text": item, "completion": "", "actions": derive_actions(item)})
        elif isinstance(item, dict):
            text = str(item.get("text", ""))
            completion = str(item.get("completion", ""))
            actions_raw = item.get("actions")

            actions: list[str] = []
            if isinstance(actions_raw, list):
                actions = [str(x) for x in actions_raw if str(x).strip()]
            elif isinstance(actions_raw, str):
                actions = [ln.strip() for ln in actions_raw.splitlines() if ln.strip()]

            # Rewrite actions if empty or generic placeholders.
            if not actions:
                actions = derive_actions(text)
            else:
                joined = "\n".join(actions).lower()
                if any(
                    p in joined
                    for p in (
                        "approved method",
                        "approved tooling",
                        "capture the exact commands",
                        "use debian cli defaults",
                    )
                ):
                    actions = derive_actions(text)

            out.append({"text": text, "completion": completion, "actions": actions})

    # keep even empty completions; app validation handles requiredness on save
    return out


def backfill(db_path: str) -> tuple[int, int]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    rows = conn.execute("SELECT record_id, version, steps_json FROM tasks").fetchall()

    changed = 0
    total = 0
    for r in rows:
        total += 1
        raw = _json_load(r["steps_json"])
        steps = normalize_steps(raw)

        # Detect whether update is needed.
        needs = False
        if isinstance(raw, list):
            for idx, it in enumerate(raw):
                if isinstance(it, dict):
                    if "actions" not in it:
                        needs = True
                        break
                    if it.get("actions") is None:
                        needs = True
                        break
                    if isinstance(it.get("actions"), list):
                        if len(it.get("actions")) == 0:
                            needs = True
                            break
                        # If actions are placeholder/generic, rewrite with Debian-biased defaults.
                        joined = "\n".join([str(x) for x in it.get("actions") if x is not None]).lower()
                        if any(
                            p in joined
                            for p in (
                                "approved method",
                                "approved tooling",
                                "capture the exact commands",
                                "use debian cli defaults",
                            )
                        ):
                            needs = True
                            break
        else:
            # non-list values will be normalized; keep conservative and do nothing
            continue

        if needs:
            conn.execute(
                "UPDATE tasks SET steps_json=? WHERE record_id=? AND version=?",
                (_json_dump(steps), r["record_id"], int(r["version"])),
            )
            changed += 1

    conn.commit()
    conn.close()
    return total, changed


def main() -> None:
    # Ensure we can import app.main when running from the seed/ directory.
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

    parser = argparse.ArgumentParser()
    parser.add_argument("--db", help="Path to SQLite DB")
    parser.add_argument("--both", action="store_true", help="Backfill both demo + blank DBs")
    args = parser.parse_args()

    if not args.db and not args.both:
        raise SystemExit("Provide --db <path> or --both")

    if args.both:
        demo = os.path.join(base_dir, "data", "lcs_demo.db")
        blank = os.path.join(base_dir, "data", "lcs_blank.db")
        for p in (demo, blank):
            if not os.path.exists(p):
                print(f"skip: {p} (missing)")
                continue
            total, changed = backfill(p)
            print(f"{p}: scanned={total} changed={changed}")
        return

    db_path = args.db
    if not os.path.exists(db_path):
        raise SystemExit(f"DB not found: {db_path}")
    total, changed = backfill(db_path)
    print(f"{db_path}: scanned={total} changed={changed}")


if __name__ == "__main__":
    main()
