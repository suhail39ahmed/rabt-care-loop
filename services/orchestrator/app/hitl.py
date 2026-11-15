"""Human-in-the-loop gates: approvals, 4-eyes closure, timeouts."""

from __future__ import annotations

import secrets
import time
from typing import Any

import aiosqlite

SAFE_DEFAULTS = {
    "exceptional_closure": "keep_open",
    "econsult_send": "remind",
    "critical": "next_ladder_step",
}


async def request_approval(
    db: aiosqlite.Connection,
    case_id: str,
    action: str,
    *,
    approvers_required: int = 1,
    sla_seconds: int = 900,
    evidence: dict[str, Any] | None = None,
) -> str:
    token = secrets.token_urlsafe(16)
    now = time.time()
    await db.execute(
        """
        INSERT INTO approvals(token, case_id, action, required, created_at, due_at, status, evidence_json)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
        """,
        (
            token,
            case_id,
            action,
            approvers_required,
            now,
            now + sla_seconds,
            __import__("json").dumps(evidence or {}),
        ),
    )
    await db.commit()
    return token


async def submit_decision(
    db: aiosqlite.Connection,
    token: str,
    user_id: str,
    decision: str,
    reason: str = "",
) -> dict[str, Any]:
    cur = await db.execute("SELECT * FROM approvals WHERE token = ?", (token,))
    appr = await cur.fetchone()
    if appr is None or appr["status"] != "pending":
        raise ValueError("not pending")
    try:
        await db.execute(
            "INSERT INTO approval_votes(token, user_id, decision, reason, at) VALUES (?, ?, ?, ?, ?)",
            (token, user_id, decision, reason, time.time()),
        )
    except Exception:
        pass  # unique (token, user_id) — same user cannot vote twice
    await db.commit()

    if decision == "rejected":
        await db.execute("UPDATE approvals SET status = 'rejected' WHERE token = ?", (token,))
        await db.commit()
        return {"status": "rejected", "case_id": appr["case_id"], "action": appr["action"]}

    cur = await db.execute(
        "SELECT COUNT(DISTINCT user_id) AS n FROM approval_votes WHERE token = ? AND decision = 'approved'",
        (token,),
    )
    n = (await cur.fetchone())["n"]
    if n >= appr["required"]:
        await db.execute("UPDATE approvals SET status = 'approved' WHERE token = ?", (token,))
        await db.commit()
        return {"status": "approved", "case_id": appr["case_id"], "action": appr["action"]}
    return {"status": "pending", "case_id": appr["case_id"], "votes": n, "required": appr["required"]}


async def sweep_timeouts(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    now = time.time()
    cur = await db.execute(
        "SELECT * FROM approvals WHERE status = 'pending' AND due_at < ?", (now,)
    )
    rows = await cur.fetchall()
    applied = []
    for r in rows:
        await db.execute("UPDATE approvals SET status = 'timeout' WHERE token = ?", (r["token"],))
        applied.append(
            {
                "token": r["token"],
                "case_id": r["case_id"],
                "action": r["action"],
                "safe_default": SAFE_DEFAULTS.get(r["action"], "keep_open"),
            }
        )
    await db.commit()
    return applied


async def enqueue(
    db: aiosqlite.Connection,
    case_id: str,
    kind: str,
    title: str,
    *,
    urgency: str | None = None,
    detail: str = "",
    ladder_step: int = 0,
) -> str:
    import uuid

    qid = f"q-{uuid.uuid4().hex[:10]}"
    await db.execute(
        """
        INSERT INTO queue_items(id, case_id, kind, urgency, title, detail, ladder_step, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)
        """,
        (qid, case_id, kind, urgency, title, detail, ladder_step, time.time()),
    )
    await db.commit()
    return qid


async def list_queue(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    cur = await db.execute(
        "SELECT * FROM queue_items WHERE status = 'open' ORDER BY created_at ASC"
    )
    return [dict(r) for r in await cur.fetchall()]
