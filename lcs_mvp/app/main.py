from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from pypdf import PdfReader
from fastapi import FastAPI, Form, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

Status = Literal["draft", "submitted", "confirmed", "deprecated"]
Role = Literal["viewer", "author", "reviewer", "admin"]

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "lcs.db")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")

LMSTUDIO_BASE_URL = os.environ.get("LCS_LMSTUDIO_BASE_URL", "http://127.0.0.1:1234").rstrip("/")
LMSTUDIO_MODEL = os.environ.get("LCS_LMSTUDIO_MODEL", "mistralai/mistral-7b-instruct-v0.3")

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

app = FastAPI(title="Learning Content System MVP")


@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException):
    """Prefer HTML error details for browser flows.

    FastAPI's default is JSON, which often shows up as a generic "Internal Server Error" page
    in a normal browser POST flow.
    """
    accept = (request.headers.get("accept") or "").lower()
    if "text/html" in accept and str(request.url.path).startswith("/import/pdf"):
        # Render the import form again, but include the error detail.
        return templates.TemplateResponse(
            request,
            "import_pdf.html",
            {
                "lmstudio_base_url": LMSTUDIO_BASE_URL,
                "lmstudio_model": LMSTUDIO_MODEL,
                "error": str(exc.detail),
            },
            status_code=exc.status_code,
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all so browser users get *some* error text instead of a blank 500 page."""
    import traceback

    # Always log the traceback to stdout so uvicorn logs capture it.
    traceback.print_exc()

    accept = (request.headers.get("accept") or "").lower()
    if "text/html" in accept and str(request.url.path).startswith("/import/pdf"):
        return templates.TemplateResponse(
            request,
            "import_pdf.html",
            {
                "lmstudio_base_url": LMSTUDIO_BASE_URL,
                "lmstudio_model": LMSTUDIO_MODEL,
                "error": f"Unhandled error: {type(exc).__name__}: {exc}",
            },
            status_code=500,
        )

    return JSONResponse(
        status_code=500,
        content={"detail": f"Unhandled error: {type(exc).__name__}: {exc}"},
    )


static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# --- RBAC (MVP) ---

DEFAULT_USER = "anon"
DEFAULT_ROLE: Role = "author"

ROLE_ORDER: dict[Role, int] = {
    "viewer": 0,
    "author": 1,
    "reviewer": 2,
    "admin": 3,
}


def _get_role(request: Request) -> Role:
    role = request.cookies.get("lcs_role", DEFAULT_ROLE)
    if role not in ROLE_ORDER:
        return DEFAULT_ROLE
    return role  # type: ignore[return-value]


def _get_user(request: Request) -> str:
    u = (request.cookies.get("lcs_user") or DEFAULT_USER).strip()
    return u or DEFAULT_USER


def can(role: Role, action: str) -> bool:
    """Very small RBAC matrix.

    Actions:
      - task:create, task:revise, task:submit, task:confirm
      - workflow:create, workflow:revise, workflow:submit, workflow:confirm
      - import:pdf
    """
    if role == "admin":
        return True

    if action.endswith(":confirm"):
        return role in ("reviewer",)

    if action.endswith(":submit"):
        return role in ("author",)

    if action.endswith(":create") or action.endswith(":revise"):
        return role in ("author",)

    if action == "import:pdf":
        return role in ("author",)

    return False


def require(role: Role, action: str) -> None:
    if not can(role, action):
        raise HTTPException(status_code=403, detail=f"Forbidden: requires permission {action}")


class RBACMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.user = _get_user(request)
        request.state.role = _get_role(request)
        return await call_next(request)


app.add_middleware(RBACMiddleware)

# make permission checks available in templates
templates.env.globals["can"] = can


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def db() -> sqlite3.Connection:
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks (
              record_id TEXT NOT NULL,
              version INTEGER NOT NULL,
              status TEXT NOT NULL,

              title TEXT NOT NULL,
              outcome TEXT NOT NULL,
              facts_json TEXT NOT NULL,
              concepts_json TEXT NOT NULL,
              procedure_name TEXT NOT NULL,
              steps_json TEXT NOT NULL,
              dependencies_json TEXT NOT NULL,
              irreversible_flag INTEGER NOT NULL,
              task_assets_json TEXT NOT NULL,

              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              created_by TEXT NOT NULL,
              updated_by TEXT NOT NULL,
              reviewed_at TEXT,
              reviewed_by TEXT,
              change_note TEXT,

              needs_review_flag INTEGER NOT NULL DEFAULT 0,
              needs_review_note TEXT,

              PRIMARY KEY (record_id, version)
            );

            CREATE TABLE IF NOT EXISTS workflows (
              record_id TEXT NOT NULL,
              version INTEGER NOT NULL,
              status TEXT NOT NULL,

              title TEXT NOT NULL,
              objective TEXT NOT NULL,

              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              created_by TEXT NOT NULL,
              updated_by TEXT NOT NULL,
              reviewed_at TEXT,
              reviewed_by TEXT,
              change_note TEXT,

              needs_review_flag INTEGER NOT NULL DEFAULT 0,
              needs_review_note TEXT,

              PRIMARY KEY (record_id, version)
            );

            CREATE TABLE IF NOT EXISTS workflow_task_refs (
              workflow_record_id TEXT NOT NULL,
              workflow_version INTEGER NOT NULL,
              order_index INTEGER NOT NULL,
              task_record_id TEXT NOT NULL,
              task_version INTEGER NOT NULL,

              PRIMARY KEY (workflow_record_id, workflow_version, order_index),
              FOREIGN KEY (workflow_record_id, workflow_version)
                REFERENCES workflows(record_id, version)
                ON DELETE CASCADE,
              FOREIGN KEY (task_record_id, task_version)
                REFERENCES tasks(record_id, version)
                ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS audit_log (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              entity_type TEXT NOT NULL,
              record_id TEXT NOT NULL,
              version INTEGER NOT NULL,
              action TEXT NOT NULL,
              actor TEXT NOT NULL,
              at TEXT NOT NULL,
              note TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
            CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status);
            """
        )


@app.on_event("startup")
def _startup() -> None:
    init_db()


# --- Linting (warnings-only) ---

ABSTRACT_VERBS = {
    "edit",
    "configure",
    "set up",
    "setup",
    "manage",
    "ensure",
    "handle",
    "prepare",
    "troubleshoot",
}

STATE_CHANGE_VERBS = {
    "install",
    "mount",
    "enable",
    "add",
    "update",
    "remove",
    "create",
    "delete",
}


def _normalize_steps(raw: Any) -> list[dict[str, str]]:
    """Return steps as list of {text, completion}.

    Backward compatible with legacy storage of steps as list[str].
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        out: list[dict[str, str]] = []
        for item in raw:
            if isinstance(item, str):
                out.append({"text": item, "completion": ""})
            elif isinstance(item, dict):
                out.append({"text": str(item.get("text", "")), "completion": str(item.get("completion", ""))})
        # Drop empty rows
        return [s for s in out if s.get("text") or s.get("completion")]
    return []


def lint_steps(steps: Any) -> list[str]:
    warnings: list[str] = []

    normalized = _normalize_steps(steps)

    for i, step in enumerate(normalized, start=1):
        s = step.get("text", "")
        low = s.strip().lower()

        # Abstract/bundling verbs
        for v in ABSTRACT_VERBS:
            if low.startswith(v + " ") or low == v:
                if not re.search(r"`.+?`", s) and not re.search(
                    r"\b(confirm|verify|check)\b", low
                ):
                    warnings.append(
                        f"Step {i}: starts with abstract verb '{v}'. Prefer decomposed steps with explicit method + completion check."
                    )
                break

        # Multi-action detector
        if re.search(r"\b(and|then|also|as well as)\b", low):
            warnings.append(
                f"Step {i}: may include multiple actions (contains conjunction like 'and/then/also'). Consider splitting."
            )

        # Verification expectation
        if any(low.startswith(v + " ") or low == v for v in STATE_CHANGE_VERBS):
            if not re.search(r"\b(confirm|verify|check)\b", low) and not re.search(r"`.+?`", s):
                warnings.append(
                    f"Step {i}: appears to change state; include an explicit confirmation check (command/UI observable) or follow with a check step."
                )

    return warnings


def _zip_steps(step_text: list[str], step_completion: list[str]) -> list[dict[str, str]]:
    # Keep ordering.
    out: list[dict[str, str]] = []
    for t, c in zip(step_text, step_completion, strict=False):
        out.append({"text": (t or "").strip(), "completion": (c or "").strip()})
    # If lists are mismatched, extend with remaining text.
    if len(step_text) > len(step_completion):
        for t in step_text[len(step_completion):]:
            out.append({"text": (t or "").strip(), "completion": ""})
    elif len(step_completion) > len(step_text):
        for c in step_completion[len(step_text):]:
            out.append({"text": "", "completion": (c or "").strip()})
    # Drop empty rows
    return [s for s in out if s["text"] or s["completion"]]


def _validate_steps_required(steps: list[dict[str, str]]) -> None:
    """Enforce step atomicity contract: both step text and completion are required."""
    if not steps:
        raise HTTPException(status_code=400, detail="At least one step is required")
    for idx, st in enumerate(steps, start=1):
        if not (st.get("text") or "").strip():
            raise HTTPException(status_code=400, detail=f"Step {idx}: step text is required")
        if not (st.get("completion") or "").strip():
            raise HTTPException(status_code=400, detail=f"Step {idx}: completion text is required")


# --- Helpers ---


def _pdf_extract_pages(pdf_path: str) -> list[dict[str, Any]]:
    reader = PdfReader(pdf_path)
    pages: list[dict[str, Any]] = []
    for idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append({"page": idx, "text": text})
    return pages


def _chunk_text(pages: list[dict[str, Any]], max_chars: int = 12000) -> list[dict[str, Any]]:
    """Chunk by character count, preserving page numbers."""
    chunks: list[dict[str, Any]] = []
    buf: list[str] = []
    buf_pages: list[int] = []
    size = 0

    def flush():
        nonlocal buf, buf_pages, size
        if not buf:
            return
        chunks.append({"pages": sorted(set(buf_pages)), "text": "\n\n".join(buf).strip()})
        buf, buf_pages, size = [], [], 0

    for p in pages:
        t = (p.get("text") or "").strip()
        if not t:
            continue
        header = f"[PAGE {p['page']}]"
        block = header + "\n" + t
        if size + len(block) > max_chars and buf:
            flush()
        buf.append(block)
        buf_pages.append(int(p["page"]))
        size += len(block)

    flush()
    return chunks


def _lmstudio_chat(messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int = 2000) -> str:
    """Call LM Studio local server.

    NOTE: Some LM Studio model prompt templates only support `user` + `assistant` roles.
    We normalize away `system` by prepending it to the first user message.

    Supports both:
      - OpenAI-compatible: POST /v1/chat/completions
      - LM Studio API: POST /api/v1/chat

    Returns the assistant content.
    """

    # Normalize roles: merge system content into first user message.
    sys_parts: list[str] = []
    norm: list[dict[str, str]] = []
    for m in messages:
        role = (m.get("role") or "").strip()
        content = m.get("content") or ""
        if role == "system":
            if content.strip():
                sys_parts.append(content.strip())
            continue
        if role not in ("user", "assistant"):
            # drop unknown roles in MVP
            continue
        norm.append({"role": role, "content": content})

    if sys_parts:
        sys_blob = "\n\n".join(sys_parts)
        if norm and norm[0]["role"] == "user":
            norm[0]["content"] = f"SYSTEM INSTRUCTIONS:\n{sys_blob}\n\n" + (norm[0]["content"] or "")
        else:
            norm.insert(0, {"role": "user", "content": f"SYSTEM INSTRUCTIONS:\n{sys_blob}"})

    payload = {
        "model": LMSTUDIO_MODEL,
        "messages": norm,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        with httpx.Client(timeout=httpx.Timeout(300.0, connect=30.0)) as client:
            r = client.post(f"{LMSTUDIO_BASE_URL}/v1/chat/completions", json=payload)
            if r.status_code == 404:
                # Fallback to LM Studio API (only when OpenAI-compatible endpoint is absent)
                r2 = client.post(f"{LMSTUDIO_BASE_URL}/api/v1/chat", json=payload)
                if r2.status_code >= 400:
                    raise HTTPException(
                        status_code=502,
                        detail=f"LM Studio API error {r2.status_code}: {r2.text[:500]}",
                    )
                data2 = r2.json()
                if isinstance(data2, dict) and "choices" in data2:
                    return data2["choices"][0]["message"]["content"]
                if isinstance(data2, dict) and "message" in data2 and isinstance(data2["message"], dict):
                    return data2["message"].get("content", "")
                return json.dumps(data2)

            if r.status_code >= 400:
                raise HTTPException(
                    status_code=502,
                    detail=f"LM Studio OpenAI-compatible error {r.status_code}: {r.text[:500]}",
                )

            data = r.json()
            return data["choices"][0]["message"]["content"]
    except httpx.ReadTimeout as e:
        raise HTTPException(status_code=504, detail=f"LM Studio timed out: {e}")
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"LM Studio connection error: {e}")
    except httpx.HTTPError as e:
        # Catch-all for other httpx failures
        raise HTTPException(status_code=502, detail=f"LM Studio HTTP error: {e}")


def _json_load(s: str) -> Any:
    return json.loads(s) if s else None


def _json_dump(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False)


def audit(entity_type: str, record_id: str, version: int, action: str, actor: str, note: str | None = None) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO audit_log(entity_type, record_id, version, action, actor, at, note) VALUES (?,?,?,?,?,?,?)",
            (entity_type, record_id, version, action, actor, utc_now_iso(), note),
        )


def get_latest_version(conn: sqlite3.Connection, table: str, record_id: str) -> int | None:
    row = conn.execute(
        f"SELECT MAX(version) AS v FROM {table} WHERE record_id=?", (record_id,)
    ).fetchone()
    return int(row["v"]) if row and row["v"] is not None else None


def require_can_edit(status: str) -> None:
    # Legacy guardrail (we now treat *all* records as immutable and always create new versions).
    if status == "confirmed":
        raise HTTPException(
            status_code=409,
            detail="Confirmed records are immutable. Create a new version.",
        )


def parse_lines(text: str) -> list[str]:
    # Accept either newline-separated steps or JSON-ish list pasted.
    lines = [ln.strip() for ln in text.splitlines()]
    return [ln for ln in lines if ln]


# --- Routes ---


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


@app.post("/login")
def login_set(user: str = Form(DEFAULT_USER), role: str = Form(DEFAULT_ROLE)):
    # Basic validation
    user = (user or DEFAULT_USER).strip() or DEFAULT_USER
    role_val: Role = DEFAULT_ROLE
    if role in ROLE_ORDER:
        role_val = role  # type: ignore[assignment]

    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie("lcs_user", user, httponly=False, samesite="lax")
    resp.set_cookie("lcs_role", role_val, httponly=False, samesite="lax")
    return resp


@app.post("/logout")
def logout():
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie("lcs_user")
    resp.delete_cookie("lcs_role")
    return resp


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request,
        "home.html",
        {},
    )


@app.get("/import/pdf", response_class=HTMLResponse)
def import_pdf_form(request: Request):
    require(request.state.role, "import:pdf")
    return templates.TemplateResponse(
        request,
        "import_pdf.html",
        {
            "lmstudio_base_url": LMSTUDIO_BASE_URL,
            "lmstudio_model": LMSTUDIO_MODEL,
        },
    )


@app.post("/import/pdf")
def import_pdf_run(
    request: Request,
    pdf: UploadFile = File(...),
    max_tasks: int = Form(20),
    max_chunks: int = Form(8),
    actor_note: str = Form("Imported from PDF"),
):
    require(request.state.role, "import:pdf")
    actor = request.state.user

    # Save upload
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", pdf.filename or "upload.pdf")
    file_id = str(uuid.uuid4())
    out_path = os.path.join(UPLOADS_DIR, f"{file_id}__{safe_name}")
    with open(out_path, "wb") as f:
        f.write(pdf.file.read())

    pages = _pdf_extract_pages(out_path)
    chunks = _chunk_text(pages, max_chars=12000)
    if not chunks:
        raise HTTPException(status_code=400, detail="No extractable text found in PDF")

    max_tasks = max(1, min(int(max_tasks), 200))
    max_chunks = max(1, min(int(max_chunks), 200))

    # Prompt: ask for tasks only; concepts best-effort; must include completion checks.
    system = {
        "role": "system",
        "content": (
            "You are extracting governed learning Tasks from technical documentation. "
            "You MUST follow the schema strictly. Do not invent steps that are not supported by the provided source. "
            "If uncertain, omit. Every step MUST include a completion check. "
            "Concepts are best-effort and should be minimal."
        ),
    }

    user_prompt_tpl = (
        "From the following SOURCE TEXT (with page markers), propose up to {per_chunk} Task records.\n\n"
        "Rules:\n"
        "- A Task is one atomic outcome.\n"
        "- Provide: title, outcome, facts[], concepts[], dependencies[], procedure_name.\n"
        "- Provide steps[] where each step has: text, completion.\n"
        "- Steps and completion MUST be concrete and verifiable.\n"
        "- Do NOT include troubleshooting.\n"
        "- Do NOT duplicate tasks that are semantically identical to ones already proposed earlier.\n"
        "- Return JSON ONLY: {{\"tasks\": [ ... ]}} (no markdown, no commentary).\n\n"
        "SOURCE TEXT:\n{source}\n"
    )

    # Multi-chunk: map over chunks, aggregate tasks.
    aggregate: list[dict[str, Any]] = []
    seen_titles: set[str] = set()

    # Simple quota split
    per_chunk = max(1, (max_tasks + max_chunks - 1) // max_chunks)

    for chunk in chunks[:max_chunks]:
        if len(aggregate) >= max_tasks:
            break

        # Avoid str.format() here so that any literal braces in the prompt (e.g. JSON examples)
        # can never trigger KeyError/ValueError.
        user_prompt = (
            user_prompt_tpl.replace("{per_chunk}", str(per_chunk)).replace("{source}", chunk["text"])
        )

        try:
            raw = _lmstudio_chat(
                [system, {"role": "user", "content": user_prompt}],
                temperature=0.2,
                max_tokens=2500,
            )
        except HTTPException:
            # If one chunk fails (timeout/model hiccup), continue (MVP).
            continue

        try:
            data = json.loads(raw)
        except Exception:
            # If one chunk returns non-JSON, continue (MVP).
            continue

        tasks = data.get("tasks") if isinstance(data, dict) else None
        if not isinstance(tasks, list):
            continue

        for t in tasks:
            if not isinstance(t, dict):
                continue
            title = str(t.get("title", "")).strip()
            if not title:
                continue
            key = re.sub(r"\s+", " ", title).strip().lower()
            if key in seen_titles:
                continue
            seen_titles.add(key)
            aggregate.append(t)
            if len(aggregate) >= max_tasks:
                break

    if not aggregate:
        raise HTTPException(status_code=502, detail="Model did not return any tasks across processed chunks")

    created_ids: list[str] = []
    now = utc_now_iso()

    with db() as conn:
        for t in aggregate[:max_tasks]:
            if not isinstance(t, dict):
                continue

            title = str(t.get("title", "")).strip()
            outcome = str(t.get("outcome", "")).strip()
            procedure_name = str(t.get("procedure_name", "")).strip() or title
            facts = t.get("facts") or []
            concepts = t.get("concepts") or []
            deps = t.get("dependencies") or []
            steps = t.get("steps") or []

            steps_norm = _normalize_steps(steps)
            _validate_steps_required(steps_norm)

            record_id = str(uuid.uuid4())
            version = 1

            # Attach source as a task asset for MVP traceability
            assets = [
                {
                    "url": f"source:{os.path.basename(out_path)}",
                    "type": "link",
                    "label": f"source_pdf:{safe_name}",
                }
            ]

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
                    record_id,
                    version,
                    "draft",
                    title,
                    outcome,
                    _json_dump([str(x) for x in facts]),
                    _json_dump([str(x) for x in concepts]),
                    procedure_name,
                    _json_dump(steps_norm),
                    _json_dump([str(x) for x in deps]),
                    0,
                    _json_dump(assets),
                    now,
                    now,
                    actor,
                    actor,
                    None,
                    None,
                    actor_note.strip() or "Imported from PDF",
                    1,
                    "AI-imported: concepts likely need human review",
                ),
            )
            audit("task", record_id, version, "create", actor, note="import:pdf")
            created_ids.append(record_id)

    return RedirectResponse(url="/tasks?status=draft", status_code=303)


# ---- Tasks ----


@app.get("/tasks", response_class=HTMLResponse)
def tasks_list(request: Request, status: str | None = None):
    with db() as conn:
        q = "SELECT record_id, MAX(version) AS latest_version FROM tasks GROUP BY record_id ORDER BY record_id"
        rows = conn.execute(q).fetchall()

        items = []
        for r in rows:
            rid = r["record_id"]
            latest_v = int(r["latest_version"])
            latest = conn.execute(
                "SELECT * FROM tasks WHERE record_id=? AND version=?", (rid, latest_v)
            ).fetchone()
            if not latest:
                continue
            if status and latest["status"] != status:
                continue
            # derived: update_pending_confirmation
            confirmed_v = conn.execute(
                "SELECT MAX(version) AS v FROM tasks WHERE record_id=? AND status='confirmed'",
                (rid,),
            ).fetchone()["v"]
            update_pending = False
            if confirmed_v is not None and latest_v > int(confirmed_v) and latest["status"] in ("draft", "submitted"):
                update_pending = True

            items.append(
                {
                    "record_id": rid,
                    "latest_version": latest_v,
                    "title": latest["title"],
                    "status": latest["status"],
                    "needs_review_flag": bool(latest["needs_review_flag"]),
                    "update_pending_confirmation": update_pending,
                }
            )

    return templates.TemplateResponse(
        request,
        "tasks_list.html",
        {"items": items, "status": status},
    )


@app.get("/tasks/new", response_class=HTMLResponse)
def task_new_form(request: Request):
    require(request.state.role, "task:create")
    return templates.TemplateResponse(request, "task_edit.html", {"mode": "new", "task": None, "warnings": []})


@app.post("/tasks/new")
def task_create(
    request: Request,
    title: str = Form(...),
    outcome: str = Form(...),
    procedure_name: str = Form(...),
    facts: str = Form(""),
    concepts: str = Form(""),
    dependencies: str = Form(""),
    step_text: list[str] = Form([]),
    step_completion: list[str] = Form([]),
    irreversible_flag: bool = Form(False),
):
    require(request.state.role, "task:create")
    actor = request.state.user
    record_id = str(uuid.uuid4())
    version = 1

    facts_list = parse_lines(facts)
    concepts_list = parse_lines(concepts)
    deps_list = parse_lines(dependencies)
    steps_list = _zip_steps(step_text, step_completion)
    _validate_steps_required(steps_list)

    warnings = lint_steps(steps_list)

    now = utc_now_iso()
    with db() as conn:
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
                record_id,
                version,
                "draft",
                title.strip(),
                outcome.strip(),
                _json_dump(facts_list),
                _json_dump(concepts_list),
                procedure_name.strip(),
                _json_dump(steps_list),
                _json_dump(deps_list),
                1 if irreversible_flag else 0,
                _json_dump([]),
                now,
                now,
                actor,
                actor,
                None,
                None,
                None,
                0,
                None,
            ),
        )
    audit("task", record_id, version, "create", actor)

    # Show edit page with warnings banner
    return RedirectResponse(url=f"/tasks/{record_id}/{version}/edit?created=1", status_code=303)


@app.get("/tasks/{record_id}/{version}", response_class=HTMLResponse)
def task_view(request: Request, record_id: str, version: int):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE record_id=? AND version=?", (record_id, version)
        ).fetchone()
    if not row:
        raise HTTPException(404)

    task = dict(row)
    task["facts"] = _json_load(task["facts_json"])
    task["concepts"] = _json_load(task["concepts_json"])
    task["dependencies"] = _json_load(task["dependencies_json"])

    raw_steps = _json_load(task["steps_json"])
    task["steps"] = _normalize_steps(raw_steps)

    warnings = lint_steps(task["steps"])

    return templates.TemplateResponse(
        request,
        "task_view.html",
        {"task": task, "warnings": warnings},
    )


@app.get("/tasks/{record_id}/{version}/edit", response_class=HTMLResponse)
def task_edit_form(request: Request, record_id: str, version: int):
    require(request.state.role, "task:revise")
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE record_id=? AND version=?", (record_id, version)
        ).fetchone()
    if not row:
        raise HTTPException(404)

    task = dict(row)
    task["facts"] = "\n".join(_json_load(task["facts_json"]) or [])
    task["concepts"] = "\n".join(_json_load(task["concepts_json"]) or [])
    task["dependencies"] = "\n".join(_json_load(task["dependencies_json"]) or [])

    raw_steps = _json_load(task["steps_json"])
    task["steps"] = _normalize_steps(raw_steps)

    warnings = lint_steps(task["steps"])
    return templates.TemplateResponse(
        request,
        "task_edit.html",
        {"mode": "edit", "task": task, "warnings": warnings},
    )


@app.post("/tasks/{record_id}/{version}/save")
def task_save(
    request: Request,
    record_id: str,
    version: int,
    title: str = Form(...),
    outcome: str = Form(...),
    procedure_name: str = Form(...),
    facts: str = Form(""),
    concepts: str = Form(""),
    dependencies: str = Form(""),
    step_text: list[str] = Form([]),
    step_completion: list[str] = Form([]),
    irreversible_flag: bool = Form(False),
    change_note: str = Form(""),
):
    """Records are immutable.

    Saving changes always creates a NEW VERSION (draft) with a required change_note.
    """
    require(request.state.role, "task:revise")
    actor = request.state.user

    facts_list = parse_lines(facts)
    concepts_list = parse_lines(concepts)
    deps_list = parse_lines(dependencies)
    steps_list = _zip_steps(step_text, step_completion)
    _validate_steps_required(steps_list)

    note = change_note.strip()
    if not note:
        raise HTTPException(status_code=400, detail="change_note is required when creating a new version")

    with db() as conn:
        src = conn.execute(
            "SELECT * FROM tasks WHERE record_id=? AND version=?", (record_id, version)
        ).fetchone()
        if not src:
            raise HTTPException(404)

        # New version number is latest + 1
        latest_v = get_latest_version(conn, "tasks", record_id) or version
        new_v = latest_v + 1
        now = utc_now_iso()

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
                record_id,
                new_v,
                "draft",
                title.strip(),
                outcome.strip(),
                _json_dump(facts_list),
                _json_dump(concepts_list),
                procedure_name.strip(),
                _json_dump(steps_list),
                _json_dump(deps_list),
                1 if irreversible_flag else 0,
                src["task_assets_json"],
                now,
                now,
                actor,
                actor,
                None,
                None,
                note,
                int(src["needs_review_flag"]),
                src["needs_review_note"],
            ),
        )

    audit("task", record_id, new_v, "new_version", actor, note=f"from v{version}: {note}")
    return RedirectResponse(url=f"/tasks/{record_id}/{new_v}", status_code=303)


@app.post("/tasks/{record_id}/{version}/new-version")
def task_new_version(request: Request, record_id: str, version: int):
    require(request.state.role, "task:revise")
    actor = request.state.user
    with db() as conn:
        src = conn.execute(
            "SELECT * FROM tasks WHERE record_id=? AND version=?", (record_id, version)
        ).fetchone()
        if not src:
            raise HTTPException(404)
        latest_v = get_latest_version(conn, "tasks", record_id) or version
        new_v = latest_v + 1
        now = utc_now_iso()

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
                record_id,
                new_v,
                "draft",
                src["title"],
                src["outcome"],
                src["facts_json"],
                src["concepts_json"],
                src["procedure_name"],
                src["steps_json"],
                src["dependencies_json"],
                src["irreversible_flag"],
                src["task_assets_json"],
                now,
                now,
                actor,
                actor,
                None,
                None,
                f"Created new version from v{version}",
                int(src["needs_review_flag"]),
                src["needs_review_note"],
            ),
        )

    audit("task", record_id, new_v, "new_version", actor, note=f"from v{version}")
    return RedirectResponse(url=f"/tasks/{record_id}/{new_v}/edit", status_code=303)


@app.post("/tasks/{record_id}/{version}/submit")
def task_submit(request: Request, record_id: str, version: int):
    require(request.state.role, "task:submit")
    actor = request.state.user
    with db() as conn:
        row = conn.execute(
            "SELECT status FROM tasks WHERE record_id=? AND version=?", (record_id, version)
        ).fetchone()
        if not row:
            raise HTTPException(404)
        if row["status"] != "draft":
            raise HTTPException(409, detail="Only draft tasks can be submitted")
        conn.execute(
            "UPDATE tasks SET status='submitted', updated_at=?, updated_by=? WHERE record_id=? AND version=?",
            (utc_now_iso(), actor, record_id, version),
        )
    audit("task", record_id, version, "submit", actor)
    return RedirectResponse(url=f"/tasks/{record_id}/{version}", status_code=303)


@app.post("/tasks/{record_id}/{version}/confirm")
def task_confirm(request: Request, record_id: str, version: int):
    require(request.state.role, "task:confirm")
    actor = request.state.user
    with db() as conn:
        row = conn.execute(
            "SELECT status FROM tasks WHERE record_id=? AND version=?", (record_id, version)
        ).fetchone()
        if not row:
            raise HTTPException(404)
        if row["status"] != "submitted":
            raise HTTPException(409, detail="Only submitted tasks can be confirmed")

        # Deprecate any previously confirmed version
        conn.execute(
            "UPDATE tasks SET status='deprecated', updated_at=?, updated_by=? WHERE record_id=? AND status='confirmed'",
            (utc_now_iso(), actor, record_id),
        )

        conn.execute(
            """
            UPDATE tasks
            SET status='confirmed', reviewed_at=?, reviewed_by=?, updated_at=?, updated_by=?
            WHERE record_id=? AND version=?
            """,
            (utc_now_iso(), actor, utc_now_iso(), actor, record_id, version),
        )

    audit("task", record_id, version, "confirm", actor)
    return RedirectResponse(url=f"/tasks/{record_id}/{version}", status_code=303)


# ---- Workflows ----


@app.get("/workflows", response_class=HTMLResponse)
def workflows_list(request: Request, status: str | None = None):
    with db() as conn:
        q = "SELECT record_id, MAX(version) AS latest_version FROM workflows GROUP BY record_id ORDER BY record_id"
        rows = conn.execute(q).fetchall()

        items = []
        for r in rows:
            rid = r["record_id"]
            latest_v = int(r["latest_version"])
            latest = conn.execute(
                "SELECT * FROM workflows WHERE record_id=? AND version=?", (rid, latest_v)
            ).fetchone()
            if not latest:
                continue
            if status and latest["status"] != status:
                continue

            # Derived readiness
            refs = conn.execute(
                "SELECT task_record_id, task_version FROM workflow_task_refs WHERE workflow_record_id=? AND workflow_version=? ORDER BY order_index",
                (rid, latest_v),
            ).fetchall()
            readiness = workflow_readiness(conn, [(x["task_record_id"], int(x["task_version"])) for x in refs])

            items.append(
                {
                    "record_id": rid,
                    "latest_version": latest_v,
                    "title": latest["title"],
                    "status": latest["status"],
                    "readiness": readiness,
                }
            )

    return templates.TemplateResponse(
        request,
        "workflows_list.html",
        {"items": items, "status": status},
    )


@app.get("/workflows/new", response_class=HTMLResponse)
def workflow_new_form(request: Request):
    require(request.state.role, "workflow:create")
    with db() as conn:
        confirmed_tasks = conn.execute(
            "SELECT record_id, version, title FROM tasks WHERE status='confirmed' ORDER BY title"
        ).fetchall()
    return templates.TemplateResponse(
        request,
        "workflow_edit.html",
        {"mode": "new", "workflow": None, "confirmed_tasks": confirmed_tasks, "refs_text": ""},
    )


def _parse_task_refs(task_refs: str) -> list[tuple[str, int]]:
    """Parse newline-separated: record_id@version."""
    refs: list[tuple[str, int]] = []
    for ln in parse_lines(task_refs):
        if "@" not in ln:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid task reference '{ln}'. Use the format record_id@version, one per line.",
            )
        rid, ver = ln.split("@", 1)
        try:
            refs.append((rid.strip(), int(ver.strip())))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid task version in '{ln}'. Use the format record_id@version.",
            )
    if not refs:
        raise HTTPException(status_code=400, detail="Workflow must include at least one confirmed Task reference")
    return refs


def workflow_readiness(conn: sqlite3.Connection, refs: list[tuple[str, int]]) -> Literal[
    "ready", "awaiting_task_confirmation", "invalid"
]:
    """Derived status based on referenced Task version statuses.

    Rules:
      - If any reference is missing => invalid
      - If any reference is deprecated => invalid
      - Else if any reference is not confirmed (draft/submitted) => awaiting_task_confirmation
      - Else => ready
    """
    awaiting = False

    for rid, ver in refs:
        row = conn.execute(
            "SELECT status FROM tasks WHERE record_id=? AND version=?", (rid, ver)
        ).fetchone()
        if not row:
            return "invalid"
        st = row["status"]
        if st == "deprecated":
            return "invalid"
        if st != "confirmed":
            awaiting = True

    return "awaiting_task_confirmation" if awaiting else "ready"


def enforce_workflow_ref_rules(conn: sqlite3.Connection, refs: list[tuple[str, int]]) -> None:
    """Hard constraints for workflow composition.

    Canonical rule (per docs): Workflows may reference ONLY confirmed Task versions.
    """
    derived = workflow_readiness(conn, refs)
    if derived == "invalid":
        raise HTTPException(
            status_code=409,
            detail="Workflow contains invalid Task references (missing or deprecated task versions)",
        )
    if derived == "awaiting_task_confirmation":
        raise HTTPException(
            status_code=409,
            detail="Workflow may reference confirmed Task versions only. Confirm referenced Tasks, then try again.",
        )


@app.post("/workflows/new")
def workflow_create(
    request: Request,
    title: str = Form(...),
    objective: str = Form(...),
    task_refs: str = Form(""),
):
    require(request.state.role, "workflow:create")
    actor = request.state.user
    record_id = str(uuid.uuid4())
    version = 1
    now = utc_now_iso()

    refs = _parse_task_refs(task_refs)

    with db() as conn:
        enforce_workflow_ref_rules(conn, refs)

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
                record_id,
                version,
                "draft",
                title.strip(),
                objective.strip(),
                now,
                now,
                actor,
                actor,
                None,
                None,
                None,
                0,
                None,
            ),
        )
        for idx, (rid, ver) in enumerate(refs, start=1):
            conn.execute(
                """
                INSERT INTO workflow_task_refs(workflow_record_id, workflow_version, order_index, task_record_id, task_version)
                VALUES (?,?,?,?,?)
                """,
                (record_id, version, idx, rid, ver),
            )

    audit("workflow", record_id, version, "create", actor)
    return RedirectResponse(url=f"/workflows/{record_id}/{version}", status_code=303)


@app.get("/workflows/{record_id}/{version}", response_class=HTMLResponse)
def workflow_view(request: Request, record_id: str, version: int):
    with db() as conn:
        wf = conn.execute(
            "SELECT * FROM workflows WHERE record_id=? AND version=?", (record_id, version)
        ).fetchone()
        if not wf:
            raise HTTPException(404)
        refs = conn.execute(
            """
            SELECT r.order_index, t.record_id, t.version, t.title, t.status as task_status
            FROM workflow_task_refs r
            JOIN tasks t ON t.record_id=r.task_record_id AND t.version=r.task_version
            WHERE r.workflow_record_id=? AND r.workflow_version=?
            ORDER BY r.order_index
            """,
            (record_id, version),
        ).fetchall()

        readiness = workflow_readiness(
            conn,
            [(r["record_id"], int(r["version"])) for r in refs],
        )

    return templates.TemplateResponse(
        request,
        "workflow_view.html",
        {"workflow": dict(wf), "refs": refs, "readiness": readiness},
    )


@app.get("/workflows/{record_id}/{version}/revise", response_class=HTMLResponse)
def workflow_revise_form(request: Request, record_id: str, version: int):
    require(request.state.role, "workflow:revise")
    with db() as conn:
        wf = conn.execute(
            "SELECT * FROM workflows WHERE record_id=? AND version=?", (record_id, version)
        ).fetchone()
        if not wf:
            raise HTTPException(404)
        refs = conn.execute(
            """
            SELECT r.order_index, r.task_record_id, r.task_version
            FROM workflow_task_refs r
            WHERE r.workflow_record_id=? AND r.workflow_version=?
            ORDER BY r.order_index
            """,
            (record_id, version),
        ).fetchall()
        confirmed_tasks = conn.execute(
            "SELECT record_id, version, title FROM tasks WHERE status='confirmed' ORDER BY title"
        ).fetchall()

    refs_text = "\n".join([f"{r['task_record_id']}@{r['task_version']}" for r in refs])
    return templates.TemplateResponse(
        request,
        "workflow_edit.html",
        {
            "mode": "revise",
            "workflow": dict(wf),
            "confirmed_tasks": confirmed_tasks,
            "refs_text": refs_text,
        },
    )


@app.post("/workflows/{record_id}/{version}/revise")
def workflow_revise(
    request: Request,
    record_id: str,
    version: int,
    title: str = Form(...),
    objective: str = Form(...),
    task_refs: str = Form(""),
    change_note: str = Form(""),
):
    require(request.state.role, "workflow:revise")
    actor = request.state.user

    note = change_note.strip()
    if not note:
        raise HTTPException(status_code=400, detail="change_note is required when creating a new version")

    refs = _parse_task_refs(task_refs)

    with db() as conn:
        src = conn.execute(
            "SELECT * FROM workflows WHERE record_id=? AND version=?", (record_id, version)
        ).fetchone()
        if not src:
            raise HTTPException(404)

        enforce_workflow_ref_rules(conn, refs)

        latest_v = get_latest_version(conn, "workflows", record_id) or version
        new_v = latest_v + 1
        now = utc_now_iso()

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
                record_id,
                new_v,
                "draft",
                title.strip(),
                objective.strip(),
                now,
                now,
                actor,
                actor,
                None,
                None,
                note,
                int(src["needs_review_flag"]),
                src["needs_review_note"],
            ),
        )

        for idx, (rid, ver) in enumerate(refs, start=1):
            conn.execute(
                """
                INSERT INTO workflow_task_refs(workflow_record_id, workflow_version, order_index, task_record_id, task_version)
                VALUES (?,?,?,?,?)
                """,
                (record_id, new_v, idx, rid, ver),
            )

    audit("workflow", record_id, new_v, "new_version", actor, note=f"from v{version}: {note}")
    return RedirectResponse(url=f"/workflows/{record_id}/{new_v}", status_code=303)


@app.post("/workflows/{record_id}/{version}/submit")
def workflow_submit(request: Request, record_id: str, version: int):
    require(request.state.role, "workflow:submit")
    actor = request.state.user
    with db() as conn:
        row = conn.execute(
            "SELECT status FROM workflows WHERE record_id=? AND version=?", (record_id, version)
        ).fetchone()
        if not row:
            raise HTTPException(404)
        if row["status"] != "draft":
            raise HTTPException(409, detail="Only draft workflows can be submitted")
        conn.execute(
            "UPDATE workflows SET status='submitted', updated_at=?, updated_by=? WHERE record_id=? AND version=?",
            (utc_now_iso(), actor, record_id, version),
        )
    audit("workflow", record_id, version, "submit", actor)
    return RedirectResponse(url=f"/workflows/{record_id}/{version}", status_code=303)


@app.post("/workflows/{record_id}/{version}/confirm")
def workflow_confirm(request: Request, record_id: str, version: int):
    require(request.state.role, "workflow:confirm")
    actor = request.state.user
    with db() as conn:
        row = conn.execute(
            "SELECT status FROM workflows WHERE record_id=? AND version=?", (record_id, version)
        ).fetchone()
        if not row:
            raise HTTPException(404)
        if row["status"] != "submitted":
            raise HTTPException(409, detail="Only submitted workflows can be confirmed")

        # Deprecate any previously confirmed version
        conn.execute(
            "UPDATE workflows SET status='deprecated', updated_at=?, updated_by=? WHERE record_id=? AND status='confirmed'",
            (utc_now_iso(), actor, record_id),
        )

        conn.execute(
            """
            UPDATE workflows
            SET status='confirmed', reviewed_at=?, reviewed_by=?, updated_at=?, updated_by=?
            WHERE record_id=? AND version=?
            """,
            (utc_now_iso(), actor, utc_now_iso(), actor, record_id, version),
        )

    audit("workflow", record_id, version, "confirm", actor)
    return RedirectResponse(url=f"/workflows/{record_id}/{version}", status_code=303)


@app.get("/workflows/{record_id}/{version}/export.md")
def workflow_export_md(record_id: str, version: int):
    with db() as conn:
        wf = conn.execute(
            "SELECT * FROM workflows WHERE record_id=? AND version=?", (record_id, version)
        ).fetchone()
        if not wf:
            raise HTTPException(404)
        refs = conn.execute(
            """
            SELECT r.order_index, t.*
            FROM workflow_task_refs r
            JOIN tasks t ON t.record_id=r.task_record_id AND t.version=r.task_version
            WHERE r.workflow_record_id=? AND r.workflow_version=?
            ORDER BY r.order_index
            """,
            (record_id, version),
        ).fetchall()

        readiness = workflow_readiness(
            conn,
            [(r["record_id"], int(r["version"])) for r in refs],
        )

    lines: list[str] = []
    lines.append(f"# {wf['title']}")
    lines.append("")

    if readiness != "ready":
        lines.append("> **DRAFT EXPORT** — This workflow contains Task versions that are not confirmed.")
        lines.append(f"> Derived readiness: `{readiness}`")
        lines.append("")

    lines.append(f"**Objective:** {wf['objective']}")
    lines.append("")

    for r in refs:
        steps = _normalize_steps(_json_load(r["steps_json"]))
        facts = _json_load(r["facts_json"]) or []
        concepts = _json_load(r["concepts_json"]) or []
        deps = _json_load(r["dependencies_json"]) or []

        lines.append(f"## Task {r['order_index']}: {r['title']} ({r['record_id']}@{r['version']})")
        if r["status"] != "confirmed":
            lines.append(f"**Task status:** {r['status']} (unconfirmed)")
            lines.append("")
        lines.append("")
        lines.append(f"**Outcome:** {r['outcome']}")
        lines.append("")

        if facts:
            lines.append("**Facts:**")
            for f in facts:
                lines.append(f"- {f}")
            lines.append("")

        if concepts:
            lines.append("**Concepts:**")
            for c in concepts:
                lines.append(f"- {c}")
            lines.append("")

        if deps:
            lines.append("**Dependencies:**")
            for d in deps:
                lines.append(f"- {d}")
            lines.append("")

        lines.append(f"**Procedure:** {r['procedure_name']}")
        lines.append("")
        for i, st in enumerate(steps, start=1):
            txt = st.get("text", "")
            comp = st.get("completion", "")
            lines.append(f"{i}. {txt}")
            if comp:
                lines.append(f"   - Completion: {comp}")
        lines.append("")

    md = "\n".join(lines)
    return HTMLResponse(content=md, media_type="text/markdown")
