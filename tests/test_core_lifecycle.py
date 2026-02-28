from __future__ import annotations

import re

from fastapi.testclient import TestClient


def _create_workflow(client: TestClient, task_record_id: str, task_version: int) -> tuple[str, int]:
    r = client.post(
        "/workflows/new",
        data={
            "title": "Workflow A",
            "objective": "Objective A",
            "task_refs": f"{task_record_id}@{task_version}",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    loc = r.headers.get("location", "")
    m = re.search(r"/workflows/([0-9a-f-]+)/(\d+)$", loc)
    assert m, f"unexpected create workflow redirect: {loc}"
    return m.group(1), int(m.group(2))


def test_task_submit_rejects_unauthorized_domain(client: TestClient, login, create_task) -> None:
    login("jjoplin", "password2")
    rid, ver = create_task("aws")

    r = client.post(f"/tasks/{rid}/{ver}/submit")
    assert r.status_code == 403
    assert "not authorized for domain 'aws'" in r.json()["detail"]


def test_task_submit_then_confirm_happy_path(client: TestClient, login, logout, create_task) -> None:
    login("jjoplin", "password2")
    rid, ver = create_task("debian")

    r_submit = client.post(f"/tasks/{rid}/{ver}/submit", follow_redirects=False)
    assert r_submit.status_code == 303

    logout()
    login("jhendrix", "password1")

    r_confirm = client.post(f"/tasks/{rid}/{ver}/confirm", follow_redirects=False)
    assert r_confirm.status_code == 303

    r_status = client.get(f"/tasks/{rid}/{ver}/status")
    assert r_status.status_code == 200
    assert r_status.json()["status"] == "confirmed"


def test_task_full_lifecycle_return_and_resubmit(client: TestClient, login, logout, create_task) -> None:
    login("jjoplin", "password2")
    rid, ver1 = create_task("debian")

    r_submit_v1 = client.post(f"/tasks/{rid}/{ver1}/submit", follow_redirects=False)
    assert r_submit_v1.status_code == 303

    logout()
    login("jhendrix", "password1")

    r_return_v1 = client.post(
        f"/tasks/{rid}/{ver1}/return",
        data={"note": "Please add clearer verification wording."},
        follow_redirects=False,
    )
    assert r_return_v1.status_code == 303

    logout()
    login("jjoplin", "password2")

    r_save_v2 = client.post(
        f"/tasks/{rid}/{ver1}/save",
        data={
            "title": "Task for debian v2",
            "outcome": "Outcome updated after review",
            "procedure_name": "procedure",
            "domain": "debian",
            "facts": "Fact A",
            "concepts": "Concept A",
            "dependencies": "Dependency A",
            "step_text": ["Do thing"],
            "step_completion": ["Thing is done and verified"],
            "step_actions": ["echo done"],
            "step_notes": [""],
            "change_note": "Addressed reviewer return note with clearer completion proof.",
        },
        follow_redirects=False,
    )
    assert r_save_v2.status_code == 303
    loc = r_save_v2.headers.get("location", "")
    m = re.search(rf"/tasks/{rid}/(\d+)$", loc)
    assert m, f"unexpected revise redirect: {loc}"
    ver2 = int(m.group(1))
    assert ver2 == ver1 + 1

    r_submit_v2 = client.post(f"/tasks/{rid}/{ver2}/submit", follow_redirects=False)
    assert r_submit_v2.status_code == 303

    logout()
    login("jhendrix", "password1")

    r_confirm_v2 = client.post(f"/tasks/{rid}/{ver2}/confirm", follow_redirects=False)
    assert r_confirm_v2.status_code == 303

    assert client.get(f"/tasks/{rid}/{ver1}/status").json()["status"] == "returned"
    assert client.get(f"/tasks/{rid}/{ver2}/status").json()["status"] == "confirmed"


def test_workflow_confirm_blocked_until_referenced_task_confirmed(client: TestClient, login, logout, create_task) -> None:
    login("jjoplin", "password2")
    task_rid, task_ver = create_task("debian")

    r_task_submit = client.post(f"/tasks/{task_rid}/{task_ver}/submit", follow_redirects=False)
    assert r_task_submit.status_code == 303

    wf_rid, wf_ver = _create_workflow(client, task_rid, task_ver)
    r_wf_submit = client.post(f"/workflows/{wf_rid}/{wf_ver}/submit", follow_redirects=False)
    assert r_wf_submit.status_code == 303

    logout()
    login("jhendrix", "password1")

    r_wf_confirm_blocked = client.post(f"/workflows/{wf_rid}/{wf_ver}/confirm")
    assert r_wf_confirm_blocked.status_code == 409
    assert "Task versions must be confirmed" in r_wf_confirm_blocked.json()["detail"]

    r_task_confirm = client.post(f"/tasks/{task_rid}/{task_ver}/confirm", follow_redirects=False)
    assert r_task_confirm.status_code == 303

    r_wf_confirm = client.post(f"/workflows/{wf_rid}/{wf_ver}/confirm", follow_redirects=False)
    assert r_wf_confirm.status_code == 303

    r_status = client.get(f"/workflows/{wf_rid}/{wf_ver}/status")
    assert r_status.status_code == 200
    assert r_status.json()["status"] == "confirmed"
