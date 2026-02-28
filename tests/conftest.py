from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

import pytest
from fastapi.testclient import TestClient

import lcs_mvp.app.main as app_main


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    data_dir = tmp_path / "data"
    uploads_dir = data_dir / "uploads"
    exports_dir = data_dir / "exports"
    data_dir.mkdir(parents=True, exist_ok=True)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)

    db_default = data_dir / "lcs_blueprinted_org.db"
    db_blank = data_dir / "lcs_blank.db"

    monkeypatch.setattr(app_main, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(app_main, "UPLOADS_DIR", str(uploads_dir))
    monkeypatch.setattr(app_main, "EXPORTS_DIR", str(exports_dir))
    monkeypatch.setattr(app_main, "DB_DEBIAN_PATH", str(db_default))
    monkeypatch.setattr(app_main, "DB_BLANK_PATH", str(db_blank))
    monkeypatch.setattr(app_main, "DB_OLD_DEBIAN_PATH", str(data_dir / "lcs_debian.db"))
    monkeypatch.setattr(app_main, "DB_DEMO_LEGACY_PATH", str(data_dir / "lcs_demo.db"))

    app_main.DB_PATH_CTX.set(str(db_default))
    app_main.DB_KEY_CTX.set(app_main.DB_KEY_DEBIAN)
    app_main.init_db()

    with TestClient(app_main.app) as c:
        yield c


@pytest.fixture
def login(client: TestClient) -> Callable[[str, str], None]:
    def _login(username: str, password: str) -> None:
        r = client.post(
            "/login",
            data={"username": username, "password": password},
            follow_redirects=False,
        )
        assert r.status_code == 303

    return _login


@pytest.fixture
def logout(client: TestClient) -> Callable[[], None]:
    def _logout() -> None:
        r = client.post("/logout", follow_redirects=False)
        assert r.status_code == 303

    return _logout


@pytest.fixture
def create_task(client: TestClient) -> Callable[[str], tuple[str, int]]:
    def _create_task(domain: str) -> tuple[str, int]:
        r = client.post(
            "/tasks/new",
            data={
                "title": f"Task for {domain}",
                "outcome": "Outcome",
                "procedure_name": "procedure",
                "domain": domain,
                "facts": "Fact A",
                "concepts": "Concept A",
                "dependencies": "Dependency A",
                "step_text": ["Do thing"],
                "step_completion": ["Thing is done"],
                "step_actions": ["echo done"],
                "step_notes": [""],
            },
            follow_redirects=False,
        )
        assert r.status_code == 303
        loc = r.headers.get("location", "")
        m = re.search(r"/tasks/([0-9a-f-]+)/(\d+)/edit", loc)
        assert m, f"unexpected create task redirect: {loc}"
        return m.group(1), int(m.group(2))

    return _create_task
