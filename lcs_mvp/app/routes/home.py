from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..config import templates, STALENESS_DAYS
from ..database import db, _active_domains, _user_domains
from ..audit import _normalize_domains
from ..analytics import _compute_admin_panels, _count_entity_status, _system_health_metrics
from ..utils import _json_load

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    role = request.state.role
    user = request.state.user

    cards: list[dict[str, Any]] = []
    with db() as conn:
        # viewer, audit, and content_publisher are domain-less roles: they cannot
        # be assigned domains and are implicitly granted visibility across all domains.
        _domain_agnostic = role in ("admin", "viewer", "audit", "content_publisher")
        doms = _active_domains(conn) if _domain_agnostic else _user_domains(conn, user)
        dset = {d.strip().lower() for d in doms if d}
        system_health = _system_health_metrics(conn)

        admin_panels: dict[str, Any] = {}
        domain_breakdown: list[dict[str, Any]] = []
        if role == "reviewer":
            cards = [
                {"title": "Tasks outstanding for review", "value": _count_entity_status(conn, "tasks", "submitted", role, dset), "href": "/review?item_type=task"},
                {"title": "Workflows outstanding for review", "value": _count_entity_status(conn, "workflows", "submitted", role, dset), "href": "/review?item_type=workflow"},
                {"title": "Assessments outstanding for review", "value": _count_entity_status(conn, "assessment_items", "submitted", role, dset), "href": "/review?item_type=assessment"},
            ]
        elif role == "author":
            cards = [
                {"title": "Returned Tasks", "value": _count_entity_status(conn, "tasks", "returned", role, dset), "href": "/tasks?status=returned"},
                {"title": "Returned Workflows", "value": _count_entity_status(conn, "workflows", "returned", role, dset), "href": "/workflows?status=returned"},
                {"title": "Returned Assessments", "value": _count_entity_status(conn, "assessment_items", "returned", role, dset), "href": "/assessments?status=returned"},
            ]
        elif role == "assessment_author":
            cards = [
                {"title": "Returned Questions", "value": _count_entity_status(conn, "assessment_items", "returned", role, dset), "href": "/assessments?status=returned"},
                {"title": "Confirmed Tasks", "value": _count_entity_status(conn, "tasks", "confirmed", role, dset), "href": "/tasks?status=confirmed"},
                {"title": "Confirmed Workflows", "value": _count_entity_status(conn, "workflows", "confirmed", role, dset), "href": "/workflows?status=confirmed"},
                {"title": "Confirmed Assessments", "value": _count_entity_status(conn, "assessment_items", "confirmed", role, dset), "href": "/assessments?status=confirmed"},
            ]
        elif role == "admin":
            admin_panels = _compute_admin_panels(conn, doms, system_health)
            cards = []
        elif _domain_agnostic:
            cards = []
            # Build per-domain confirmed breakdown for domain-agnostic roles.
            # Each row: domain, confirmed task/workflow/assessment counts with filter hrefs.
            domain_breakdown = []
            for d in sorted(doms):
                d_lower = d.strip().lower()

                task_count = conn.execute(
                    """SELECT COUNT(*) FROM (
                        SELECT record_id, MAX(version) AS v FROM tasks GROUP BY record_id
                    ) sub JOIN tasks t ON t.record_id=sub.record_id AND t.version=sub.v
                    WHERE t.status='confirmed' AND LOWER(TRIM(COALESCE(t.domain,'')))=?""",
                    (d_lower,),
                ).fetchone()[0]

                wf_count = conn.execute(
                    """SELECT COUNT(*) FROM (
                        SELECT record_id, MAX(version) AS v FROM workflows GROUP BY record_id
                    ) sub JOIN workflows w ON w.record_id=sub.record_id AND w.version=sub.v,
                    json_each(COALESCE(w.domains_json,'[]')) je
                    WHERE w.status='confirmed' AND LOWER(TRIM(je.value))=?""",
                    (d_lower,),
                ).fetchone()[0]

                as_count = conn.execute(
                    """SELECT COUNT(*) FROM (
                        SELECT record_id, MAX(version) AS v FROM assessment_items GROUP BY record_id
                    ) sub JOIN assessment_items a ON a.record_id=sub.record_id AND a.version=sub.v,
                    json_each(COALESCE(a.domains_json,'[]')) je
                    WHERE a.status='confirmed' AND LOWER(TRIM(je.value))=?""",
                    (d_lower,),
                ).fetchone()[0]

                domain_breakdown.append({
                    "domain": d,
                    "tasks": task_count,
                    "workflows": wf_count,
                    "assessments": as_count,
                    "tasks_href": f"/tasks?status=confirmed&domain={d}",
                    "workflows_href": f"/workflows?status=confirmed&domain={d}",
                    "assessments_href": f"/assessments?status=confirmed&domain={d}",
                })
        else:
            cards = [
                {"title": "Confirmed Tasks", "value": _count_entity_status(conn, "tasks", "confirmed", role, dset), "href": "/tasks?status=confirmed"},
                {"title": "Confirmed Workflows", "value": _count_entity_status(conn, "workflows", "confirmed", role, dset), "href": "/workflows?status=confirmed"},
                {"title": "Confirmed Assessments", "value": _count_entity_status(conn, "assessment_items", "confirmed", role, dset), "href": "/assessments?status=confirmed"},
            ]
            domain_breakdown = []

        last_audit = conn.execute("SELECT at, actor, action FROM audit_log ORDER BY at DESC LIMIT 1").fetchone()

    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "cards": cards,
            "domains": doms,
            "last_audit": dict(last_audit) if last_audit else None,
            "admin_panels": admin_panels,
            "domain_breakdown": domain_breakdown,
            "system_health": system_health,
            "staleness_days": STALENESS_DAYS,
            # Role flags — computed here so templates don't embed role logic.
            "admin_mode": role == "admin",
            "reviewer_mode": role == "reviewer",
            "author_mode": role == "author",
            "assessment_author_mode": role == "assessment_author",
            "domain_agnostic_mode": role in ("viewer", "audit", "content_publisher"),
            # Admin alert values — pulled from admin_panels to avoid string-matching in template.
            "alert_blocked_workflows": admin_panels.get("alert_blocked_workflows", 0),
            "alert_returned_assessments": admin_panels.get("alert_returned_assessments", 0),
            "alert_submitted_workflows": admin_panels.get("alert_submitted_workflows", 0),
            "alert_draft_assessments": admin_panels.get("alert_draft_assessments", 0),
        },
    )


@router.get("/search", response_class=HTMLResponse)
def search(request: Request, q: str = ""):
    q_norm = (q or "").strip().lower()
    if not q_norm:
        return templates.TemplateResponse(request, "search_results.html", {"q": q, "tasks": [], "workflows": []})

    role = request.state.role
    user = request.state.user

    with db() as conn:
        doms = _active_domains(conn) if role == "admin" else _user_domains(conn, user)
        dset = {d.strip().lower() for d in doms if d}

        task_rows = conn.execute(
            "SELECT record_id, MAX(version) AS latest_version FROM tasks GROUP BY record_id ORDER BY record_id"
        ).fetchall()
        tasks: list[dict[str, Any]] = []
        for r in task_rows:
            rid = r["record_id"]
            latest_v = int(r["latest_version"])
            t = conn.execute(
                "SELECT record_id, version, title, status, domain, outcome, tags_json FROM tasks WHERE record_id=? AND version=?",
                (rid, latest_v),
            ).fetchone()
            if not t:
                continue
            domain_val = str(t["domain"] or "").strip().lower()
            if role != "admin" and domain_val not in dset:
                continue
            tags: list[str] = []  # Phase 1: tasks are tagless.
            hay = " ".join([
                str(t["record_id"] or ""),
                str(t["title"] or ""),
                str(t["outcome"] or ""),
                str(t["domain"] or ""),
            ]).lower()
            if q_norm not in hay:
                continue
            tasks.append(
                {
                    "record_id": t["record_id"],
                    "version": int(t["version"]),
                    "title": t["title"],
                    "status": t["status"],
                    "domain": t["domain"],
                    "tags": tags,
                }
            )

        wf_rows = conn.execute(
            "SELECT record_id, MAX(version) AS latest_version FROM workflows GROUP BY record_id ORDER BY record_id"
        ).fetchall()
        workflows: list[dict[str, Any]] = []
        for r in wf_rows:
            rid = r["record_id"]
            latest_v = int(r["latest_version"])
            w = conn.execute(
                "SELECT record_id, version, title, status, objective, domains_json, tags_json FROM workflows WHERE record_id=? AND version=?",
                (rid, latest_v),
            ).fetchone()
            if not w:
                continue
            wdoms = _normalize_domains(w["domains_json"])
            if role != "admin" and not dset.intersection(set(wdoms)):
                continue
            tags = [str(x).strip().lower() for x in (_json_load(w["tags_json"] or "[]") or []) if str(x).strip()]
            hay = " ".join([
                str(w["record_id"] or ""),
                str(w["title"] or ""),
                str(w["objective"] or ""),
                " ".join(wdoms),
                " ".join(tags),
            ]).lower()
            if q_norm not in hay:
                continue
            workflows.append(
                {
                    "record_id": w["record_id"],
                    "version": int(w["version"]),
                    "title": w["title"],
                    "status": w["status"],
                    "domains": wdoms,
                    "tags": tags,
                }
            )

    return templates.TemplateResponse(
        request,
        "search_results.html",
        {"q": q, "tasks": tasks, "workflows": workflows},
    )


@router.get("/explainer", response_class=HTMLResponse)
def explainer(request: Request):
    """Plain-language explainer page.

    Auth required via middleware.
    """
    return templates.TemplateResponse(request, "explainer.html", {})


@router.get("/_pulse")
def pulse(request: Request):
    """Return small operational counters for the UI pulse strip.

    Auth is required via middleware.
    """
    role = request.state.role
    user = request.state.user

    with db() as conn:
        # Task counts
        task_counts = {
            r["status"]: int(r["c"])
            for r in conn.execute("SELECT status, COUNT(*) AS c FROM tasks GROUP BY status").fetchall()
        }

        # Reviewer-scoped counts (domain entitlements)
        reviewer_pending = None
        reviewer_domains: list[str] = []
        if role in ("reviewer", "admin"):
            reviewer_domains = _user_domains(conn, user)

            if role == "admin":
                # admin sees everything
                reviewer_pending = int(
                    conn.execute(
                        "SELECT ("
                        " (SELECT COUNT(*) FROM tasks WHERE status='submitted') +"
                        " (SELECT COUNT(*) FROM workflows WHERE status='submitted') +"
                        " (SELECT COUNT(*) FROM assessment_items WHERE status='submitted')"
                        ") AS c"
                    ).fetchone()["c"]
                )
            else:
                if reviewer_domains:
                    qmarks = ",".join(["?"] * len(reviewer_domains))

                    t = int(
                        conn.execute(
                            f"SELECT COUNT(*) AS c FROM tasks WHERE status='submitted' AND domain IN ({qmarks})",
                            reviewer_domains,
                        ).fetchone()["c"]
                    )
                    # Workflows: domain match is derived via domains_json; filter in Python for portability.
                    w_rows = conn.execute(
                        "SELECT domains_json FROM workflows WHERE status='submitted'"
                    ).fetchall()
                    w = 0
                    rdset = {d.strip().lower() for d in reviewer_domains if d}
                    for wr in w_rows:
                        doms = _normalize_domains(wr["domains_json"])
                        if rdset.intersection(doms):
                            w += 1

                    # Assessments: same.
                    a_rows = conn.execute(
                        "SELECT domains_json FROM assessment_items WHERE status='submitted'"
                    ).fetchall()
                    a = 0
                    for ar in a_rows:
                        doms = _normalize_domains(ar["domains_json"])
                        if rdset.intersection(doms):
                            a += 1

                    reviewer_pending = t + w + a
                else:
                    reviewer_pending = 0

        # Workflow counts
        wf_counts = {
            r["status"]: int(r["c"])
            for r in conn.execute("SELECT status, COUNT(*) AS c FROM workflows GROUP BY status").fetchall()
        }

        # Assessment counts
        as_counts = {
            r["status"]: int(r["c"])
            for r in conn.execute("SELECT status, COUNT(*) AS c FROM assessment_items GROUP BY status").fetchall()
        }

        last_audit = conn.execute("SELECT at, actor, action FROM audit_log ORDER BY at DESC LIMIT 1").fetchone()

    return {
        "tasks": {
            "draft": task_counts.get("draft", 0),
            "submitted": task_counts.get("submitted", 0),
            "confirmed": task_counts.get("confirmed", 0),
        },
        "workflows": {
            "draft": wf_counts.get("draft", 0),
            "submitted": wf_counts.get("submitted", 0),
            "confirmed": wf_counts.get("confirmed", 0),
        },
        "assessments": {
            "draft": as_counts.get("draft", 0),
            "submitted": as_counts.get("submitted", 0),
            "confirmed": as_counts.get("confirmed", 0),
        },
        "review": {
            "pending": reviewer_pending,
            "domains": reviewer_domains,
        },
        "audit": {
            "last": dict(last_audit) if last_audit else None,
        },
    }
