"""Seed the local SQLite DB with coherent example records.

This is deliberately local-only data intended to make the MVP feel usable
for enterprise-ish demos (regulated / high-risk domains).

Run:
  cd lcs_mvp
  source .venv/bin/activate
  python3 seed/seed_demo.py

Then start the app:
  uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def j(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def main() -> None:
    # Import app init to guarantee schema is present
    from app.main import DB_PATH, init_db

    init_db()

    now = utc_now_iso()
    actor = "seed"

    # --- Tasks ---
    # Keep these as DRAFT + needs_review_flag=1: they are structure examples,
    # not clinically/security authoritative content.

    def _derive_actions(step_text: str) -> list[str]:
        import re

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

        if re.search(r"\b(record|document)\b", low):
            actions.append("Record the exact commands run and outputs captured")
            actions.append("Attach relevant evidence (log excerpt / command output)")

        if not actions:
            actions.append("Use Debian CLI defaults to perform the change")
            actions.append("Capture the exact commands and outputs as evidence")

        out: list[str] = []
        seen: set[str] = set()
        for a in actions:
            if a in seen:
                continue
            seen.add(a)
            out.append(a)
        return out

    tasks = [
        # IT / Security / Compliance
        {
            "title": "Create a break-glass local admin account with vault storage",
            "outcome": "A break-glass local admin account exists, is access-controlled, and is documented for emergency use.",
            "facts": [
                "Break-glass accounts bypass some centralized identity controls.",
                "Emergency credentials must be stored in an approved secrets vault.",
            ],
            "concepts": [
                "Break-glass access: a tightly controlled emergency access path used only when standard access fails.",
                "Least privilege: grant only what is required, even for emergency access.",
            ],
            "procedure_name": "Create and secure break-glass local admin",
            "steps": [
                {"text": "Create the local user account using the approved naming convention.", "completion": "The account appears in the local users list with the expected username."},
                {"text": "Add the account to the local Administrators group.", "completion": "Group membership shows the account in Administrators."},
                {"text": "Set a strong random password and store it in the approved secrets vault entry.", "completion": "Vault entry exists and contains the current password; a test sign-in succeeds."},
                {"text": "Enable and validate audit logging for local logons.", "completion": "A test logon generates an event in the security/audit log."},
                {"text": "Record the owner and review cadence in the break-glass register.", "completion": "Register entry exists with an owner and next review date."},
            ],
            "dependencies": [
                "Administrative access to the endpoint or server.",
                "Access to the organization secrets vault.",
            ],
            "irreversible": 0,
        },
        {
            "title": "Rotate a privileged service account password without downtime",
            "outcome": "The service account password is rotated and dependent services continue operating.",
            "facts": [
                "Services can fail if credentials change without updating all dependencies.",
                "Rotation events must be auditable.",
            ],
            "concepts": [
                "Dependency mapping: enumerate all consumers before changing credentials.",
            ],
            "procedure_name": "Rotate service account credential safely",
            "steps": [
                {"text": "Identify every system and service that authenticates using the service account.", "completion": "A dependency list exists and includes each consuming system."},
                {"text": "Generate a new password and update it in the secrets vault.", "completion": "Vault entry is updated and versioned."},
                {"text": "Update each dependent system to use the new password.", "completion": "Each dependency config is updated and saved/applied."},
                {"text": "Restart or reload dependent services where required.", "completion": "Each restarted service reports healthy state."},
                {"text": "Run end-to-end health checks and review authentication logs.", "completion": "Health checks pass and no auth failures are observed."},
            ],
            "dependencies": [
                "Access to secrets vault and service configurations.",
                "Approved maintenance window if required by policy.",
            ],
            "irreversible": 0,
        },
        {
            "title": "Approve a firewall rule change request",
            "outcome": "A firewall rule change is approved with documented risk, scope, and expiration.",
            "facts": [
                "Firewall changes can increase attack surface.",
                "Time-bound rules reduce long-lived risk.",
            ],
            "concepts": [
                "Compensating controls: additional mitigations used when risk cannot be eliminated.",
            ],
            "procedure_name": "Review and approve firewall change",
            "steps": [
                {"text": "Verify the request includes source, destination, port/protocol, and business justification.", "completion": "Request record contains all required fields."},
                {"text": "Assess risk and confirm the scope is minimal.", "completion": "Risk note is recorded and scope reduction (if any) is documented."},
                {"text": "Require an expiry/TTL for the rule.", "completion": "Request includes an explicit expiry date/time."},
                {"text": "Obtain required approver sign-off per policy.", "completion": "Approver identity and timestamp are recorded."},
                {"text": "Authorize implementation and link the change ticket to the firewall object.", "completion": "Change ticket references the firewall rule identifier."},
            ],
            "dependencies": [
                "Change request exists in the ticketing system.",
                "Requester provided complete technical details.",
            ],
            "irreversible": 0,
        },

        # Healthcare (example structure; not medical advice)
        {
            "title": "Administer a high-alert medication with independent double-check",
            "outcome": "A high-alert medication dose is administered with dual verification and documentation completed.",
            "facts": [
                "High-alert medications carry increased risk of harm if used in error.",
                "Independent double-checks reduce calculation and administration errors.",
            ],
            "concepts": [
                "Independent double-check: two qualified clinicians verify key parameters separately.",
            ],
            "procedure_name": "Administer high-alert medication with dual verification",
            "steps": [
                {"text": "Confirm patient identity using two approved identifiers.", "completion": "Patient identity matches the order in the chart."},
                {"text": "Verify medication order details (drug, dose, route, time) against the chart.", "completion": "Order details match the prepared medication label."},
                {"text": "Perform an independent double-check with a second qualified clinician.", "completion": "Second clinician documents verification of drug, dose, and route."},
                {"text": "Administer the medication via the ordered route using aseptic technique.", "completion": "Dose is delivered and administration time is recorded."},
                {"text": "Monitor and document patient response per protocol.", "completion": "Required observations are recorded within the required time window."},
            ],
            "dependencies": [
                "Valid medication order exists.",
                "A second qualified clinician is available.",
            ],
            "irreversible": 1,
        },

        # Aviation / Safety-critical ops (example structure)
        {
            "title": "Perform a pre-flight walkaround inspection (single aircraft)",
            "outcome": "A pre-flight walkaround inspection is completed and discrepancies are documented.",
            "facts": [
                "Pre-flight inspections are required by regulation/operator policy.",
                "Discrepancies must be documented before dispatch.",
            ],
            "concepts": [
                "Airworthiness: an aircraft must meet defined conditions before flight.",
            ],
            "procedure_name": "Conduct pre-flight walkaround",
            "steps": [
                {"text": "Review the aircraft technical log for open defects and deferred items.", "completion": "Technical log review is recorded and open items are identified."},
                {"text": "Inspect exterior surfaces for obvious damage and leaks.", "completion": "Walkaround checklist item is marked complete with notes for any findings."},
                {"text": "Confirm required covers/pins are removed per checklist.", "completion": "Covers/pins status is confirmed and recorded."},
                {"text": "Verify tyres and landing gear condition visually.", "completion": "Gear/tyre checklist items are completed with any discrepancies noted."},
                {"text": "Document any discrepancy and follow the operator’s defect reporting path.", "completion": "A discrepancy entry exists or a statement of 'no defects found' is recorded."},
            ],
            "dependencies": [
                "Access to the aircraft and the current walkaround checklist.",
                "Authority to record defects in the technical log.",
            ],
            "irreversible": 0,
        },
    ]

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    # Insert tasks, track ids for workflow refs
    inserted: list[tuple[str, int, str]] = []  # (record_id, version, title)

    for t in tasks:
        # Ensure steps include optional actions
        steps_out = []
        for st in t.get("steps", []):
            if isinstance(st, dict):
                text = str(st.get("text", ""))
                completion = str(st.get("completion", ""))
                actions = st.get("actions")
                if actions is None:
                    actions = _derive_actions(text)
                steps_out.append({"text": text, "completion": completion, "actions": actions})
            else:
                steps_out.append({"text": str(st), "completion": "", "actions": _derive_actions(str(st))})
        t["steps"] = steps_out

        rid = str(uuid.uuid4())
        ver = 1
        conn.execute(
            """
            INSERT INTO tasks(
              record_id, version, status,
              title, outcome, facts_json, concepts_json, procedure_name, steps_json, dependencies_json,
              irreversible_flag, task_assets_json,
              created_at, updated_at, created_by, updated_by,
              reviewed_at, reviewed_by, change_note,
              needs_review_flag, needs_review_note
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                rid,
                ver,
                "draft",
                t["title"],
                t["outcome"],
                j(t["facts"]),
                j(t["concepts"]),
                t["procedure_name"],
                j(t["steps"]),
                j(t["dependencies"]),
                int(t["irreversible"]),
                j([]),
                now,
                now,
                actor,
                actor,
                None,
                None,
                "seed data",
                1,
                "Seeded example; review for correctness",
            ),
        )
        inserted.append((rid, ver, t["title"]))

    # --- Workflows ---
    # Workflows can reference draft tasks (authoring rule). We'll create 2 draft workflows.

    def task_id_by_title(substr: str) -> tuple[str, int]:
        for rid, ver, title in inserted:
            if substr.lower() in title.lower():
                return rid, ver
        raise RuntimeError(f"seed task not found: {substr}")

    workflows = [
        {
            "title": "Establish emergency access controls for endpoints",
            "objective": "Emergency access paths exist and are governed to reduce operational risk.",
            "refs": [
                task_id_by_title("break-glass"),
                task_id_by_title("firewall"),
            ],
        },
        {
            "title": "Operate under high-risk administration constraints",
            "objective": "High-risk work is executed with verification, logging, and documented accountability.",
            "refs": [
                task_id_by_title("service account"),
                task_id_by_title("high-alert"),
            ],
        },
    ]

    for wf in workflows:
        wid = str(uuid.uuid4())
        wv = 1
        conn.execute(
            """
            INSERT INTO workflows(
              record_id, version, status,
              title, objective,
              created_at, updated_at, created_by, updated_by,
              reviewed_at, reviewed_by, change_note,
              needs_review_flag, needs_review_note
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                wid,
                wv,
                "draft",
                wf["title"],
                wf["objective"],
                now,
                now,
                actor,
                actor,
                None,
                None,
                "seed data",
                1,
                "Seeded example; review for correctness",
            ),
        )
        for idx, (trid, tver) in enumerate(wf["refs"], start=1):
            conn.execute(
                """
                INSERT INTO workflow_task_refs(workflow_record_id, workflow_version, order_index, task_record_id, task_version)
                VALUES (?,?,?,?,?)
                """,
                (wid, wv, idx, trid, int(tver)),
            )

    conn.commit()
    conn.close()

    print(f"Seeded {len(tasks)} tasks and {len(workflows)} workflows into {DB_PATH}")


if __name__ == "__main__":
    main()
