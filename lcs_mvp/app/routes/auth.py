from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from ..config import (
    DB_KEY_BLANK, DB_KEY_COOKIE, DB_KEY_DEBIAN, UPLOADS_DIR, templates,
)
from ..auth import SESSION_COOKIE
from ..database import (
    db, utc_now_iso,
    _active_domains, _available_db_keys, _db_profile_label, _list_custom_db_keys,
    _normalize_db_key, _user_id, _user_domains,
    _verify_password, _new_session_token,
)
from ..audit import audit

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    # Show demo users and their passwords (MVP demo convenience).
    with db() as conn:
        users = conn.execute(
            "SELECT id, username, role, COALESCE(demo_password, '') AS demo_password FROM users WHERE disabled_at IS NULL ORDER BY role DESC, username ASC"
        ).fetchall()

        # Fetch domains for each user
        users_with_domains = []
        for u in users:
            user_dict = dict(u)
            if user_dict["role"] == "admin":
                user_dict["domains"] = _active_domains(conn)
            else:
                user_dict["domains"] = _user_domains(conn, user_dict["username"])
            users_with_domains.append(user_dict)

    custom = _list_custom_db_keys()
    profiles = [{"key": k, "label": _db_profile_label(k)} for k in [DB_KEY_DEBIAN, DB_KEY_BLANK] + custom]
    return templates.TemplateResponse(
        request,
        "login.html",
        {"users": users_with_domains, "profiles": profiles, "db_key": request.state.db_key},
    )


@router.post("/login")
def login_run(request: Request, username: str = Form(""), password: str = Form("")):
    username = (username or "").strip()
    password = password or ""
    if not username:
        raise HTTPException(status_code=400, detail="username is required")

    with db() as conn:
        u = conn.execute(
            """
            SELECT id, username, role, password_salt_hex, password_hash_hex
            FROM users
            WHERE username=? AND disabled_at IS NULL
            """,
            (username,),
        ).fetchone()
        if not u:
            raise HTTPException(status_code=403, detail="Invalid credentials")
        if not _verify_password(password, str(u["password_salt_hex"]), str(u["password_hash_hex"])):
            raise HTTPException(status_code=403, detail="Invalid credentials")

        token = _new_session_token()
        conn.execute(
            "INSERT INTO sessions(token, user_id, created_at) VALUES (?,?,?)",
            (token, int(u["id"]), utc_now_iso()),
        )

    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    return resp


@router.post("/logout")
def logout(request: Request):
    token = (request.cookies.get(SESSION_COOKIE) or "").strip()
    if token:
        with db() as conn:
            conn.execute("UPDATE sessions SET revoked_at=? WHERE token=? AND revoked_at IS NULL", (utc_now_iso(), token))

    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@router.post("/db/pick")
def db_pick(request: Request, db_key: str = Form(DB_KEY_DEBIAN)):
    """Unauthenticated DB profile picker for demo convenience.

    This is intentionally only a cookie setter; it does not create profiles.
    """
    key = _normalize_db_key(db_key or DB_KEY_DEBIAN)
    if key not in _available_db_keys():
        raise HTTPException(status_code=400, detail="Invalid db_key")

    resp = RedirectResponse(url="/login", status_code=303)
    resp.set_cookie(DB_KEY_COOKIE, key, httponly=False, samesite="lax")
    return resp


@router.get("/profile", response_class=HTMLResponse)
def profile_view(request: Request, msg: str | None = None):
    actor = request.state.user
    with db() as conn:
        u = conn.execute(
            "SELECT username, COALESCE(display_name,'') AS display_name, COALESCE(bio,'') AS bio, COALESCE(avatar_path,'') AS avatar_path FROM users WHERE username=? AND disabled_at IS NULL",
            (actor,),
        ).fetchone()
        if not u:
            raise HTTPException(404)

        domains = _active_domains(conn)
        uid = _user_id(conn, actor)
        selected_rows = conn.execute("SELECT domain FROM user_domains WHERE user_id=?", (uid,)).fetchall() if uid else []
        selected = {str(r["domain"]) for r in selected_rows}

    return templates.TemplateResponse(
        request,
        "profile.html",
        {"user": dict(u), "domains": domains, "selected": selected, "msg": msg, "role": request.state.role},
    )


def _avatar_file_response(avatar_path: str, *, no_store: bool) -> FileResponse:
    p = str(avatar_path or "").strip()
    if not p:
        raise HTTPException(status_code=404, detail="No avatar")

    base = Path(UPLOADS_DIR).resolve()
    f = Path(p)
    try:
        f_abs = f.resolve()
    except (ValueError, OSError):
        raise HTTPException(status_code=400, detail="Invalid avatar path")

    if base not in f_abs.parents:
        raise HTTPException(status_code=400, detail="Invalid avatar path")
    if not f_abs.exists():
        raise HTTPException(status_code=404, detail="Avatar missing")

    mt = "application/octet-stream"
    low = f_abs.name.lower()
    if low.endswith(".png"):
        mt = "image/png"
    elif low.endswith(".jpg") or low.endswith(".jpeg"):
        mt = "image/jpeg"
    elif low.endswith(".webp"):
        mt = "image/webp"

    headers = {
        "Pragma": "no-cache",
    }
    if no_store:
        headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        headers["Expires"] = "0"
    else:
        headers["Cache-Control"] = "no-cache, must-revalidate"

    return FileResponse(str(f_abs), media_type=mt, headers=headers)


@router.get("/profile/avatar")
def profile_avatar(request: Request):
    actor = request.state.user
    with db() as conn:
        row = conn.execute("SELECT COALESCE(avatar_path,'') AS avatar_path FROM users WHERE username=? AND disabled_at IS NULL", (actor,)).fetchone()
        if not row:
            raise HTTPException(404)
        p = str(row["avatar_path"] or "")
    return _avatar_file_response(p, no_store=True)


@router.get("/avatar/{username}")
def public_avatar(username: str):
    """Public avatar endpoint for login page (no auth required)."""
    with db() as conn:
        row = conn.execute("SELECT COALESCE(avatar_path,'') AS avatar_path FROM users WHERE username=? AND disabled_at IS NULL", (username,)).fetchone()
        if not row:
            raise HTTPException(404)
        p = str(row["avatar_path"] or "")
    return _avatar_file_response(p, no_store=False)


@router.post("/profile/save")
def profile_save(
    request: Request,
    display_name: str = Form(""),
    bio: str = Form(""),
    avatar: UploadFile | None = File(None),
):
    actor = request.state.user
    dn = (display_name or "").strip()
    b = (bio or "").strip()

    avatar_path = None
    if avatar is not None and avatar.filename:
        # Accept small set of image types
        ct = (avatar.content_type or "").lower()
        if ct not in ("image/png", "image/jpeg", "image/webp"):
            raise HTTPException(status_code=400, detail="Avatar must be PNG, JPG, or WebP")

        ext = ".png" if ct == "image/png" else (".webp" if ct == "image/webp" else ".jpg")
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_user = re.sub(r"[^a-zA-Z0-9_-]+", "_", actor)[:48]
        out_dir = Path(UPLOADS_DIR) / "avatars"
        out_dir.mkdir(parents=True, exist_ok=True)
        nonce = uuid4().hex[:10]
        out_path = (out_dir / f"avatar__{safe_user}__{ts}__{nonce}{ext}").resolve()

        data = avatar.file.read()
        if len(data) > 2_000_000:
            raise HTTPException(status_code=400, detail="Avatar too large (max 2MB)")
        out_path.write_bytes(data)
        avatar_path = str(out_path)

    with db() as conn:
        if avatar_path is None:
            conn.execute(
                "UPDATE users SET display_name=?, bio=? WHERE username=? AND disabled_at IS NULL",
                (dn, b, actor),
            )
        else:
            conn.execute(
                "UPDATE users SET display_name=?, bio=?, avatar_path=? WHERE username=? AND disabled_at IS NULL",
                (dn, b, avatar_path, actor),
            )
        audit("user", actor, 1, "profile_update", actor, note="profile fields updated", conn=conn)

    return RedirectResponse(url="/profile?msg=saved", status_code=303)


@router.post("/profile/domains/save")
def profile_domains_save(request: Request, domain: list[str] = Form([])):
    raise HTTPException(
        status_code=403,
        detail="Domain entitlements are admin-managed. Use the admin users page.",
    )
