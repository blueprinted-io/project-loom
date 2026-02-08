"""Backfill/normalize Task content in the demo DB to make it feel "lived in".

Goals (per user request):
- Do NOT change statuses.
- Ensure tasks have non-empty facts/concepts/procedure fields.
- Ensure every step has: text, actions(list), completion, notes(str; may be empty).
- Add a small number of pragmatic per-step notes (rare) for realism.

Run:
  cd lcs_mvp
  source .venv/bin/activate
  python3 seed/backfill_task_quality.py

Optional:
  python3 seed/backfill_task_quality.py --db data/lcs_demo.db
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json_load(s: str | None, default: Any) -> Any:
    if not s:
        return default
    try:
        return json.loads(s)
    except Exception:
        return default


def _json_dump(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False)


def _derive_actions(step_text: str) -> list[str]:
    s = (step_text or "").strip()
    if not s:
        return []

    low = s.lower()
    actions: list[str] = []

    cmds = re.findall(r"`([^`]+)`", s)
    for c in [x.strip() for x in cmds if x.strip()][:3]:
        actions.append(c)

    m = re.search(r"\b(edit|open)\s+(/[^\s]+)", s, flags=re.IGNORECASE)
    if m:
        path = m.group(2)
        actions.append(f"sudo nano {path}  # or your editor of choice")

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

    # De-dupe while preserving order
    out: list[str] = []
    seen: set[str] = set()
    for a in actions:
        if a in seen:
            continue
        seen.add(a)
        out.append(a)
    return out


def _default_fact_concept(title: str, outcome: str) -> tuple[list[str], list[str]]:
    t = (title or "").strip()
    o = (outcome or "").strip()
    low = f"{t} {o}".lower()

    facts: list[str] = []
    concepts: list[str] = []

    if any(k in low for k in ("fstab", "/etc/fstab")):
        facts += ["/etc/fstab controls persistent mounts.", "Invalid fstab entries can prevent a system from booting cleanly."]
        concepts += ["Validate mount configuration before reboot."]
    if any(k in low for k in ("mount", "findmnt")):
        facts += ["A mount attaches a filesystem to a directory in the tree."]
        concepts += ["Persistence (boot-time) and current-session mounts are separate concerns."]
    if any(k in low for k in ("apt", "package", "upgrade", "install")):
        facts += ["APT installs and upgrades packages using configured repositories.", "Upgrades can change service behavior and should be validated."]
        concepts += ["Prefer explicit confirmation checks (version/status) after package changes."]
    if any(k in low for k in ("ssh", "openssh")):
        facts += ["SSH configuration changes can lock you out if applied incorrectly."]
        concepts += ["Make changes in a way that preserves rollback access."]
    if any(k in low for k in ("systemd", "service")):
        facts += ["systemd unit files control how services start and run."]
        concepts += ["Use `systemctl status` and logs to confirm service health."]

    if not facts:
        facts = ["This task should include explicit completion checks."]
    if not concepts:
        concepts = ["Make the work repeatable by separating intent (step) from how (actions) and proof (completion)."]

    # keep small
    facts = facts[:3]
    concepts = concepts[:2]
    return facts, concepts


def _maybe_note_for_step(step_text: str) -> str:
    low = (step_text or "").lower()

    if "/etc/" in low and any(k in low for k in ("edit", "open")):
        return "If nano is not available, use another editor (e.g., vim) and preserve file formatting."

    if "apt-get" in low or "apt" in low:
        return "If you are on a minimal system without sudo, run the commands as root."

    if "ssh" in low and any(k in low for k in ("reload", "restart")):
        return "Keep an existing SSH session open until you confirm the new settings work."

    return ""


@dataclass
class Stats:
    tasks_touched: int = 0
    steps_touched: int = 0
    facts_filled: int = 0
    concepts_filled: int = 0
    actions_filled: int = 0
    notes_added: int = 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/lcs_demo.db")
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    now = utc_now_iso()
    actor = "seed_update"

    stats = Stats()

    rows = conn.execute(
        "SELECT record_id, version, title, outcome, facts_json, concepts_json, steps_json FROM tasks"
    ).fetchall()

    for r in rows:
        title = r["title"] or ""
        outcome = r["outcome"] or ""

        facts = _json_load(r["facts_json"], [])
        concepts = _json_load(r["concepts_json"], [])
        steps = _json_load(r["steps_json"], [])

        changed = False

        if not facts or not isinstance(facts, list):
            facts, _ = _default_fact_concept(title, outcome)
            stats.facts_filled += 1
            changed = True

        if not concepts or not isinstance(concepts, list):
            _, concepts = _default_fact_concept(title, outcome)
            stats.concepts_filled += 1
            changed = True

        norm_steps: list[dict[str, Any]] = []
        if not isinstance(steps, list):
            steps = []

        for st in steps:
            if isinstance(st, str):
                st = {"text": st, "completion": "", "actions": []}

            if not isinstance(st, dict):
                continue

            text = str(st.get("text", "") or "").strip()
            completion = str(st.get("completion", "") or "").strip()
            actions = st.get("actions")
            notes = str(st.get("notes", "") or "").strip()

            if actions is None or not isinstance(actions, list):
                actions = []

            if not actions:
                derived = _derive_actions(text)
                if derived:
                    actions = derived
                    stats.actions_filled += 1
                    changed = True

            if "notes" not in st:
                # Normalize presence even if blank.
                changed = True

            if not notes:
                maybe = _maybe_note_for_step(text)
                if maybe:
                    notes = maybe
                    stats.notes_added += 1
                    changed = True

            norm_steps.append({"text": text, "completion": completion, "actions": actions, "notes": notes})

        if norm_steps != steps:
            stats.steps_touched += 1
            changed = True

        if changed:
            stats.tasks_touched += 1
            conn.execute(
                """
                UPDATE tasks
                SET facts_json=?, concepts_json=?, steps_json=?, updated_at=?, updated_by=?
                WHERE record_id=? AND version=?
                """,
                (
                    _json_dump(facts),
                    _json_dump(concepts),
                    _json_dump(norm_steps),
                    now,
                    actor,
                    r["record_id"],
                    r["version"],
                ),
            )

    conn.commit()

    print("Backfill complete")
    print(stats)


if __name__ == "__main__":
    main()
