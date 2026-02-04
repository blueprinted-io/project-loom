"""Seed a reasonably large local-only corpus into lcs_mvp/data/lcs.db.

Goal: make the MVP feel like an enterprise system with enough records to stress UX.

Creates (by default):
  - 50 Tasks
  - 10 Workflows

Status mix (default):
  - Tasks: 30 draft, 20 submitted
  - Workflows: 6 draft, 4 submitted

Idempotency:
  - If any existing task has change_note == SEED_NOTE, this script will refuse to re-run
    unless you pass --force.

Run:
  cd lcs_mvp
  source .venv/bin/activate
  python3 seed/seed_large_corpus.py

Optional:
  python3 seed/seed_large_corpus.py --force

Notes:
- This is demo data. It is structurally correct, but not authoritative guidance.
- We intentionally keep records unconfirmed unless you explicitly want confirmed examples.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone


SEED_NOTE = "seed_large_corpus_v1"
ACTOR = "seed"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def j(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def _derive_actions(step_text: str) -> list[str]:
    """Aggressively derive optional actions from step text."""
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
        actions.append("sudo systemctl restart <service>  # replace <service> with the unit name")

    if re.search(r"\b(enable)\b", low) and not any("systemctl" in a for a in actions):
        actions.append("sudo systemctl enable --now <service>  # replace <service> with the unit name")

    if re.search(r"\b(install)\b", low) and not any("apt-get" in a for a in actions):
        actions.append("sudo apt-get update")
        actions.append("sudo apt-get install -y <package>  # replace <package> with the package name")

    if re.search(r"\b(record|document)\b", low):
        actions.append("Update the ticket/runbook entry with the required fields")
        actions.append("Attach evidence (log excerpt/screenshot/output) as applicable")

    if not actions:
        actions.append("Complete this step using the approved method/tooling for your environment")
        actions.append("If you used CLI commands, record the exact commands and outputs in the change record")

    out: list[str] = []
    seen: set[str] = set()
    for a in actions:
        if a in seen:
            continue
        seen.add(a)
        out.append(a)
    return out


def step(text: str, completion: str, actions: list[str] | None = None) -> dict[str, object]:
    return {"text": text, "completion": completion, "actions": actions if actions is not None else _derive_actions(text)}


def build_tasks() -> list[dict]:
    """Return 50 coherent, regulated/high-risk flavored tasks.

    Domains: IT/SecOps, Change Mgmt, Clinical ops (structure-only), Aviation/maintenance (structure-only).
    """

    tasks: list[dict] = []

    # --- IT / Security / Compliance (most of the corpus) ---
    tasks += [
        {
            "title": "Register a new privileged access request in the ticketing system",
            "outcome": "A privileged access request is recorded with scope, justification, and approver chain.",
            "facts": ["Privileged access must be time-bound and audited."],
            "concepts": ["Access governance: privileges are granted via accountable approvals."],
            "procedure_name": "Create privileged access request",
            "steps": [
                step("Create a new access request ticket using the approved template.", "Ticket exists and has a unique identifier."),
                step("Record the requested role/group and the exact systems in scope.", "Ticket includes role/group and system list."),
                step("Record business justification and requested duration.", "Ticket includes justification and expiry date/time."),
                step("Assign the ticket to the correct approver group.", "Ticket shows assigned approver group and is in review state."),
            ],
            "deps": ["Access to the ticketing system."],
            "tags": ["security", "governance"],
            "meta": {"domain": "IT", "risk_level": "high", "owner_team": "Security Operations"},
            "irreversible": 0,
        },
        {
            "title": "Approve a privileged access request",
            "outcome": "A privileged access request is approved or rejected with recorded rationale.",
            "facts": ["Approvals must be attributable to a person and timestamp."],
            "concepts": ["Least privilege: approve only the minimum required access."],
            "procedure_name": "Review and decide access request",
            "steps": [
                step("Review the request scope and justification in the ticket.", "Reviewer notes indicate the request was assessed."),
                step("Confirm the requested duration complies with policy.", "Ticket includes a compliant expiry or a rejection reason."),
                step("Approve or reject the request and record rationale.", "Ticket status changes and rationale is recorded."),
            ],
            "deps": ["A submitted privileged access request exists."],
            "tags": ["security", "approval"],
            "meta": {"domain": "IT", "risk_level": "high", "owner_team": "Security Operations"},
            "irreversible": 0,
        },
        {
            "title": "Create a change request for a production configuration update",
            "outcome": "A change request exists with implementation plan, rollback plan, and impact window.",
            "facts": ["Production changes require documented rollback."],
            "concepts": ["Change control reduces unplanned outages through review and planning."],
            "procedure_name": "Create production change request",
            "steps": [
                step("Create a change request ticket and classify it by impact.", "Change request exists with impact classification."),
                step("Document the implementation steps at a high level.", "Ticket contains an implementation plan section."),
                step("Document a rollback plan with a clear trigger.", "Ticket contains rollback plan and trigger condition."),
                step("Schedule the change window and notify stakeholders.", "Change window is set and notification is recorded."),
            ],
            "deps": ["Access to the ticketing/change system."],
            "tags": ["change-management"],
            "meta": {"domain": "IT", "risk_level": "medium", "owner_team": "Platform"},
            "irreversible": 0,
        },
        {
            "title": "Approve a production change request",
            "outcome": "A production change request is approved with accountable sign-off.",
            "facts": ["Approver sign-off is required before implementation."],
            "concepts": ["Risk assessment: changes should be evaluated for blast radius and reversibility."],
            "procedure_name": "Review production change",
            "steps": [
                step("Review implementation and rollback plans for completeness.", "Reviewer comment confirms plans are present."),
                step("Confirm the change window and stakeholder notification are appropriate.", "Ticket shows approved window and notifications."),
                step("Approve or reject the change with recorded rationale.", "Ticket status updates and rationale is recorded."),
            ],
            "deps": ["A draft change request exists."],
            "tags": ["change-management", "approval"],
            "meta": {"domain": "IT", "risk_level": "medium", "owner_team": "Platform"},
            "irreversible": 0,
        },
        {
            "title": "Create a firewall rule change request with expiration",
            "outcome": "A firewall rule request exists with minimal scope and a defined expiration.",
            "facts": ["Firewall changes may increase attack surface."],
            "concepts": ["Time-bound access reduces long-lived exposure."],
            "procedure_name": "Request firewall rule",
            "steps": [
                step("Record source, destination, port, and protocol in the request.", "Request includes source/destination/port/protocol."),
                step("Record business justification and service owner.", "Request includes justification and owner."),
                step("Set an explicit expiration date/time.", "Request includes expiration timestamp."),
                step("Attach evidence or references supporting the need.", "Request has at least one attachment or link."),
            ],
            "deps": ["Access to the change/ticket system."],
            "tags": ["security", "network"],
            "meta": {"domain": "IT", "risk_level": "high", "owner_team": "Network"},
            "irreversible": 0,
        },
        {
            "title": "Verify endpoint disk encryption is enabled",
            "outcome": "Disk encryption status is verified and recorded for the endpoint.",
            "facts": ["Encryption helps protect data at rest."],
            "concepts": ["Control verification: check controls via observable system state."],
            "procedure_name": "Verify disk encryption",
            "steps": [
                step("Run the approved command or console check for disk encryption status.", "Output shows encryption is enabled."),
                step("Record the verification result and timestamp in the asset record.", "Asset record includes status and timestamp."),
            ],
            "deps": ["Access to the endpoint management console."],
            "tags": ["security", "endpoint"],
            "meta": {"domain": "IT", "risk_level": "medium", "owner_team": "IT Operations"},
            "irreversible": 0,
        },
        {
            "title": "Quarantine a suspected compromised endpoint",
            "outcome": "The endpoint is isolated from the network while preserving evidence.",
            "facts": ["Isolation limits lateral movement."],
            "concepts": ["Incident containment: reduce spread before remediation."],
            "procedure_name": "Quarantine endpoint",
            "steps": [
                step("Place the endpoint into quarantine using the EDR/management action.", "EDR console shows device in quarantined state."),
                step("Capture key identifiers (hostname, serial, user) into the incident record.", "Incident record contains device identifiers."),
                step("Notify the incident channel and assign an owner.", "Incident channel message exists and owner is assigned."),
            ],
            "deps": ["An incident record exists."],
            "tags": ["security", "incident-response"],
            "meta": {"domain": "IT", "risk_level": "high", "owner_team": "Security Operations"},
            "irreversible": 0,
        },
        {
            "title": "Collect a volatile triage snapshot from an endpoint",
            "outcome": "A volatile triage snapshot is collected and attached to the incident record.",
            "facts": ["Volatile data may be lost after reboot."],
            "concepts": ["Evidence preservation: collect time-sensitive data early."],
            "procedure_name": "Collect volatile triage",
            "steps": [
                step("Run the approved triage collection tool on the endpoint.", "Tool completes successfully and outputs an archive."),
                step("Hash the archive using the approved hash algorithm.", "A hash value is recorded for the archive."),
                step("Upload the archive and hash to the incident evidence store.", "Evidence store contains the archive and hash."),
            ],
            "deps": ["Endpoint access and approved triage tool."],
            "tags": ["security", "forensics"],
            "meta": {"domain": "IT", "risk_level": "high", "owner_team": "Security Operations"},
            "irreversible": 0,
        },
        {
            "title": "Rotate an API key used by a production service",
            "outcome": "The API key is rotated and the service continues to authenticate successfully.",
            "facts": ["Key rotation may break services if dependencies are not updated."],
            "concepts": ["Credential dependency mapping prevents partial updates."],
            "procedure_name": "Rotate API key",
            "steps": [
                step("Identify all consumers of the API key.", "A dependency list exists for the API key."),
                step("Create a new API key in the source system.", "New key is created and has an identifier."),
                step("Update consumers to use the new key.", "Consumers are updated and deployed."),
                step("Revoke the old key after validation.", "Old key is revoked and auth logs show successful usage of new key."),
            ],
            "deps": ["Access to the API key management system."],
            "tags": ["security", "credentials"],
            "meta": {"domain": "IT", "risk_level": "high", "owner_team": "Platform"},
            "irreversible": 0,
        },
    ]

    # Expand IT/SecOps set by templating common patterns
    patterns = [
        ("Review", "an access control list update", "A requested ACL update is reviewed and decision is recorded.", "Review ACL update"),
        ("Validate", "a backup job completed successfully", "A backup job completion is validated and recorded.", "Validate backup job"),
        ("Test", "an incident notification pathway", "Incident notification channels are tested and results are recorded.", "Test incident notifications"),
        ("Document", "a system owner for a critical service", "A service owner is recorded for a critical service.", "Document service ownership"),
        ("Verify", "multi-factor authentication is enforced for admin logins", "MFA enforcement for admin logins is verified and recorded.", "Verify MFA enforcement"),
    ]
    for verb, obj, outcome, pname in patterns:
        tasks.append(
            {
                "title": f"{verb} {obj}",
                "outcome": outcome,
                "facts": ["Control checks must be auditable."],
                "concepts": ["Assurance: verify what is true, not what is assumed."],
                "procedure_name": pname,
                "steps": [
                    step(f"Identify the system records relevant to {obj}.", "Relevant records are located and referenced."),
                    step(f"Perform the approved check for {obj}.", "Check produces a recorded result."),
                    step("Record the result and timestamp in the system of record.", "Result is recorded with timestamp."),
                ],
                "deps": ["Access to the system of record."],
                "tags": ["compliance"],
                "meta": {"domain": "IT", "risk_level": "medium", "owner_team": "IT Operations"},
                "irreversible": 0,
            }
        )

    # --- Clinical operations (structure-only examples; do not treat as medical advice) ---
    clinical = [
        ("Perform handover", "A clinical handover is completed using the approved structure.", "Conduct clinical handover"),
        ("Verify patient identity", "Patient identity is verified prior to an intervention.", "Verify patient identity"),
        ("Document a critical observation", "A critical observation is recorded and escalated per policy.", "Document critical observation"),
    ]
    for title, outcome, pname in clinical:
        tasks.append(
            {
                "title": title,
                "outcome": outcome,
                "facts": ["Documentation must be complete and attributable."],
                "concepts": ["Standardization reduces omission under time pressure."],
                "procedure_name": pname,
                "steps": [
                    step("Use the approved form/template for the record.", "Record is created using the approved template."),
                    step("Complete required fields with current observations.", "Required fields are populated and saved."),
                    step("Escalate to the next role when escalation criteria are met.", "Escalation is documented with timestamp."),
                ],
                "deps": ["Access to the clinical record system."],
                "tags": ["regulated", "high-risk"],
                "meta": {"domain": "Clinical", "risk_level": "high", "owner_team": "Clinical Governance"},
                "irreversible": 1,
            }
        )

    # --- Aviation / maintenance (structure-only examples) ---
    aviation = [
        ("Record a maintenance discrepancy", "A maintenance discrepancy is recorded in the technical log.", "Record discrepancy"),
        ("Complete a pre-flight checklist", "A pre-flight checklist is completed and recorded.", "Complete pre-flight checklist"),
        ("Verify tool control before departure", "Tool inventory is verified and recorded.", "Verify tool control"),
    ]
    for title, outcome, pname in aviation:
        tasks.append(
            {
                "title": title,
                "outcome": outcome,
                "facts": ["Safety-critical work requires checklists and traceability."],
                "concepts": ["Human factors: checklists reduce omission."],
                "procedure_name": pname,
                "steps": [
                    step("Open the applicable checklist/log entry.", "Checklist/log entry is opened with a unique identifier."),
                    step("Complete each required item and record findings.", "All required items are marked complete."),
                    step("Submit the record to the system of record.", "Record is saved with timestamp and author."),
                ],
                "deps": ["Access to the technical log/checklist."],
                "tags": ["regulated", "safety"],
                "meta": {"domain": "Aviation", "risk_level": "high", "owner_team": "Maintenance"},
                "irreversible": 0,
            }
        )

    # Ensure exactly 50 tasks by adding simple compliance tasks if needed
    while len(tasks) < 50:
        idx = len(tasks) + 1
        tasks.append(
            {
                "title": f"Perform quarterly access recertification check #{idx}",
                "outcome": "Access recertification evidence is recorded for the scoped system.",
                "facts": ["Recertification is required on a defined cadence."],
                "concepts": ["Periodic review reduces access drift."],
                "procedure_name": "Perform access recertification",
                "steps": [
                    step("Export the current access list for the system.", "An export file is produced and stored."),
                    step("Obtain owner attestation for the access list.", "Owner attestation is recorded."),
                    step("File the evidence in the audit repository.", "Evidence is stored with date and scope."),
                ],
                "deps": ["System owner is identified."],
                "tags": ["compliance"],
                "meta": {"domain": "IT", "risk_level": "medium", "owner_team": "GRC"},
                "irreversible": 0,
            }
        )

    return tasks[:50]


def build_workflows(task_ids: list[tuple[str, int, dict]]) -> list[dict]:
    """Create 10 workflows referencing the seeded task ids.

    task_ids entries include (record_id, version, task_dict).
    """

    # helper: pick tasks by tag
    def pick(tag: str, n: int) -> list[tuple[str, int]]:
        out: list[tuple[str, int]] = []
        for rid, ver, t in task_ids:
            if tag in t.get("tags", []):
                out.append((rid, ver))
        return out[:n]

    security_core = pick("security", 6)
    compliance_core = pick("compliance", 6)
    change_core = pick("change-management", 4)
    incident_core = pick("incident-response", 3)

    workflows = [
        {
            "title": "Privileged access governance (request to approval)",
            "objective": "Privileged access requests are created, reviewed, and decided with auditability.",
            "refs": [security_core[0], security_core[1]],
            "tags": ["security", "governance"],
            "meta": {"domain": "IT", "risk_level": "high", "owner_team": "Security Operations"},
        },
        {
            "title": "Production change management (request to approval)",
            "objective": "Production changes are planned, reviewed, and approved with rollback defined.",
            "refs": [change_core[0], change_core[1]],
            "tags": ["change-management"],
            "meta": {"domain": "IT", "risk_level": "medium", "owner_team": "Platform"},
        },
        {
            "title": "Network exposure control (firewall rule governance)",
            "objective": "Firewall rule changes are requested with expiration and controlled approvals.",
            "refs": [security_core[2], compliance_core[0]],
            "tags": ["security", "network"],
            "meta": {"domain": "IT", "risk_level": "high", "owner_team": "Network"},
        },
        {
            "title": "Endpoint containment and triage (initial response)",
            "objective": "A suspected endpoint compromise is contained and initial evidence is collected.",
            "refs": [incident_core[0], compliance_core[1]],
            "tags": ["security", "incident-response"],
            "meta": {"domain": "IT", "risk_level": "high", "owner_team": "Security Operations"},
        },
        {
            "title": "Compliance evidence collection (recertification)",
            "objective": "Compliance evidence is collected and stored with traceability.",
            "refs": [compliance_core[2], compliance_core[3], compliance_core[4]],
            "tags": ["compliance"],
            "meta": {"domain": "IT", "risk_level": "medium", "owner_team": "GRC"},
        },
    ]

    # pad to 10 workflows using generic compositions
    i = 1
    all_refs = [(rid, ver) for rid, ver, _ in task_ids]
    cursor = 0
    while len(workflows) < 10:
        refs = all_refs[cursor:cursor + 3]
        if len(refs) < 2:
            cursor = 0
            continue
        workflows.append(
            {
                "title": f"Operational assurance workflow #{i}",
                "objective": "Operational control checks are executed and recorded.",
                "refs": refs,
                "tags": ["assurance"],
                "meta": {"domain": "IT", "risk_level": "medium", "owner_team": "IT Operations"},
            }
        )
        i += 1
        cursor += 3

    return workflows[:10]


def main() -> None:
    # Ensure lcs_mvp/ is on sys.path when running as a script from seed/
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

    from app.main import DB_PATH, init_db

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Allow reseeding even if seed marker exists")
    args = parser.parse_args()

    init_db()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    # idempotency check
    existing = conn.execute(
        "SELECT 1 FROM tasks WHERE change_note=? LIMIT 1",
        (SEED_NOTE,),
    ).fetchone()
    if existing and not args.force:
        raise SystemExit(
            f"Refusing to seed: corpus marker '{SEED_NOTE}' already present. Run with --force to reseed."
        )

    now = utc_now_iso()

    tasks = build_tasks()

    # Assign statuses
    for idx, t in enumerate(tasks):
        t["status"] = "draft" if idx < 30 else "submitted"

    # Insert tasks
    inserted_tasks: list[tuple[str, int, dict]] = []
    for t in tasks:
        rid = str(uuid.uuid4())
        ver = 1
        conn.execute(
            """
            INSERT INTO tasks(
              record_id, version, status,
              title, outcome, facts_json, concepts_json, procedure_name, steps_json, dependencies_json,
              irreversible_flag, task_assets_json,
              tags_json, meta_json,
              created_at, updated_at, created_by, updated_by,
              reviewed_at, reviewed_by, change_note,
              needs_review_flag, needs_review_note
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                rid,
                ver,
                t["status"],
                t["title"],
                t["outcome"],
                j(t.get("facts", [])),
                j(t.get("concepts", [])),
                t["procedure_name"],
                j(t.get("steps", [])),
                j(t.get("deps", [])),
                int(t.get("irreversible", 0)),
                j([]),
                j(t.get("tags", [])),
                j(t.get("meta", {})),
                now,
                now,
                ACTOR,
                ACTOR,
                None,
                None,
                SEED_NOTE,
                1,
                "Seeded corpus (structure demo); requires SME review",
            ),
        )
        inserted_tasks.append((rid, ver, t))

    # Build workflows
    workflows = build_workflows(inserted_tasks)

    for idx, wf in enumerate(workflows):
        wf["status"] = "draft" if idx < 6 else "submitted"

    for wf in workflows:
        wid = str(uuid.uuid4())
        wv = 1
        conn.execute(
            """
            INSERT INTO workflows(
              record_id, version, status,
              title, objective,
              tags_json, meta_json,
              created_at, updated_at, created_by, updated_by,
              reviewed_at, reviewed_by, change_note,
              needs_review_flag, needs_review_note
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                wid,
                wv,
                wf["status"],
                wf["title"],
                wf["objective"],
                j(wf.get("tags", [])),
                j(wf.get("meta", {})),
                now,
                now,
                ACTOR,
                ACTOR,
                None,
                None,
                SEED_NOTE,
                1,
                "Seeded corpus (structure demo); requires SME review",
            ),
        )
        for order_index, (trid, tver) in enumerate(wf["refs"], start=1):
            conn.execute(
                """
                INSERT INTO workflow_task_refs(workflow_record_id, workflow_version, order_index, task_record_id, task_version)
                VALUES (?,?,?,?,?)
                """,
                (wid, wv, order_index, trid, int(tver)),
            )

    conn.commit()
    conn.close()

    print(f"Seeded: {len(tasks)} tasks and {len(workflows)} workflows into {DB_PATH}")


if __name__ == "__main__":
    main()
