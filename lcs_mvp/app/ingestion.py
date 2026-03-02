from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import httpx
from pypdf import PdfReader
from fastapi import HTTPException

from .config import LMSTUDIO_BASE_URL, LMSTUDIO_MODEL
from .linting import _normalize_steps


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# LM Studio integration
# ---------------------------------------------------------------------------

def _lmstudio_probe(base_url: str | None = None) -> dict[str, Any]:
    """Fast health probe for LM Studio.

    Returns {ok: bool, detail: str, base_url: str}.
    """
    bu = (base_url or LMSTUDIO_BASE_URL).rstrip("/")
    try:
        with httpx.Client(timeout=httpx.Timeout(2.0, connect=1.0)) as client:
            # Prefer OpenAI-compatible endpoint; HEAD is not always supported, so use GET.
            r = client.get(f"{bu}/v1/models")
            if r.status_code < 400:
                return {"ok": True, "detail": "ok", "base_url": bu}
            # Fallback probe
            r2 = client.get(f"{bu}/api/v1/models")
            if r2.status_code < 400:
                return {"ok": True, "detail": "ok", "base_url": bu}
            return {"ok": False, "detail": f"HTTP {r.status_code}", "base_url": bu}
    except Exception as e:
        return {"ok": False, "detail": str(e), "base_url": bu}


def _lmstudio_chat(messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int = 2000, base_url: str | None = None) -> str:
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

    bu = (base_url or LMSTUDIO_BASE_URL).rstrip("/")

    try:
        with httpx.Client(timeout=httpx.Timeout(300.0, connect=30.0)) as client:
            r = client.post(f"{bu}/v1/chat/completions", json=payload)
            if r.status_code == 404:
                # Fallback to LM Studio API (only when OpenAI-compatible endpoint is absent)
                r2 = client.post(f"{bu}/api/v1/chat", json=payload)
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


# ---------------------------------------------------------------------------
# Fingerprinting and deduplication
# ---------------------------------------------------------------------------

def _sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def _short_code(prefix: str, record_id: str) -> str:
    """Deterministic short display id (for human-visible trace tags)."""
    h = hashlib.sha256((record_id or "").encode("utf-8", errors="ignore")).hexdigest().upper()
    return f"{prefix}-{h[:6]}"


def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _task_fingerprint(task: dict[str, Any]) -> str:
    """Deterministic fingerprint for exact-ish dedupe."""
    title = _norm_text(str(task.get("title", "")))
    outcome = _norm_text(str(task.get("outcome", "")))
    steps = task.get("steps") or []
    steps_norm = _normalize_steps(steps)
    parts: list[str] = [title, outcome]
    for st in steps_norm:
        parts.append(_norm_text(str(st.get("text", ""))))
        parts.append(_norm_text(str(st.get("completion", ""))))
    raw = "\n".join(parts).encode("utf-8", errors="ignore")
    return _sha256_bytes(raw)


def _extract_step_targets(steps: list[dict[str, Any]]) -> set[str]:
    """Extract rough targets for near-duplicate hints (paths, services, packages)."""
    targets: set[str] = set()
    path_re = re.compile(r"(/etc/[^\s]+|/var/[^\s]+|/usr/[^\s]+|/opt/[^\s]+)")
    svc_re = re.compile(r"\b(systemctl)\s+(restart|reload|enable|disable)\s+([a-zA-Z0-9_.@-]+)")
    pkg_re = re.compile(r"\bapt(-get)?\s+install\s+(-y\s+)?([a-zA-Z0-9+_.:-]+)")

    for st in steps or []:
        t = (st.get("text") or "") + "\n" + (st.get("completion") or "")
        for m in path_re.findall(t):
            targets.add(m.lower())
        for m in svc_re.findall(t):
            targets.add(f"service:{m[2].lower()}")
        for m in pkg_re.findall(t):
            targets.add(f"pkg:{m[2].lower()}")
    return targets


def _near_duplicate_score(a: dict[str, Any], b: dict[str, Any]) -> float:
    """Heuristic similarity score in [0,1]."""
    a_steps = _normalize_steps(a.get("steps") or [])
    b_steps = _normalize_steps(b.get("steps") or [])

    a_title = set(_norm_text(str(a.get("title", ""))).split())
    b_title = set(_norm_text(str(b.get("title", ""))).split())
    a_out = set(_norm_text(str(a.get("outcome", ""))).split())
    b_out = set(_norm_text(str(b.get("outcome", ""))).split())

    def jacc(x: set[str], y: set[str]) -> float:
        if not x and not y:
            return 0.0
        return len(x & y) / max(1, len(x | y))

    title_sim = jacc(a_title, b_title)
    out_sim = jacc(a_out, b_out)

    a_tgt = _extract_step_targets(a_steps)
    b_tgt = _extract_step_targets(b_steps)
    tgt_sim = jacc(a_tgt, b_tgt)

    # Weighted: outcome + targets matter more than title.
    return 0.20 * title_sim + 0.45 * out_sim + 0.35 * tgt_sim
