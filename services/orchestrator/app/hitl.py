"""Human-in-the-loop gates: approvals, 4-eyes closure, timeouts."""

from __future__ import annotations

import json
import secrets
import sqlite3
from typing import Any

import aiosqlite

from app import demo_clock

SAFE_DEFAULTS = {
    "exceptional_closure": "keep_open",
    "econsult_send": "remind",
    "critical": "next_ladder_step",
}


class ApprovalError(ValueError):
    """Client-facing approval rejection (maps to 4xx)."""


async def request_approval(
    db: aiosqlite.Connection,
    case_id: str,
    action: str,
    *,
    approvers_required: int = 1,
    sla_seconds: int = 900,
    evidence: dict[str, Any] | None = None,
    requested_by: str | None = None,
) -> str:
    token = secrets.token_urlsafe(16)
    now = demo_clock.now()
    await db.execute(
        """
        INSERT INTO approvals(token, case_id, action, required, created_at, due_at, status, evidence_json, requested_by)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        """,
        (
            token,
            case_id,
            action,
            approvers_required,
            now,
            now + sla_seconds,
            json.dumps(evidence or {}),
            requested_by,
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
        raise ApprovalError("not pending")

    requested_by = appr["requested_by"]
    if requested_by and user_id == requested_by:
        raise ApprovalError("requester cannot approve their own request")

    try:
        await db.execute(
            "INSERT INTO approval_votes(token, user_id, decision, reason, at) VALUES (?, ?, ?, ?, ?)",
            (token, user_id, decision, reason, demo_clock.now()),
        )
        await db.commit()
    except sqlite3.IntegrityError:
        # Same user voting twice — keep the first vote; count once
        pass

    if decision == "rejected":
        # Only reject if this user's (first) vote is reject; duplicate inserts are ignored
        cur = await db.execute(
            "SELECT decision FROM approval_votes WHERE token = ? AND user_id = ?",
            (token, user_id),
        )
        row = await cur.fetchone()
        if row and row["decision"] == "rejected":
            await db.execute("UPDATE approvals SET status = 'rejected' WHERE token = ?", (token,))
            await db.commit()
            return {"status": "rejected", "case_id": appr["case_id"], "action": appr["action"]}

    cur = await db.execute(
        "SELECT COUNT(DISTINCT user_id) AS n FROM approval_votes WHERE token = ? AND decision = 'approved'",
        (token,),
    )
    n = (await cur.fetchone())["n"]
    if n >= appr["required"]:
        # Do NOT mark approved yet — caller must apply the case transition first (#25).
        return {
            "status": "threshold_met",
            "case_id": appr["case_id"],
            "action": appr["action"],
            "token": token,
            "votes": n,
            "required": appr["required"],
            "requested_by": requested_by,
            "evidence": json.loads(appr["evidence_json"] or "{}"),
        }
    return {
        "status": "pending",
        "case_id": appr["case_id"],
        "action": appr["action"],
        "votes": n,
        "required": appr["required"],
        "token": token,
    }


async def mark_approved(db: aiosqlite.Connection, token: str) -> None:
    await db.execute("UPDATE approvals SET status = 'approved' WHERE token = ? AND status = 'pending'", (token,))
    await db.commit()


async def list_approvals(db: aiosqlite.Connection, *, status: str = "pending") -> list[dict[str, Any]]:
    cur = await db.execute(
        "SELECT * FROM approvals WHERE status = ? ORDER BY created_at ASC",
        (status,),
    )
    rows = await cur.fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        vcur = await db.execute(
            "SELECT user_id, decision, reason, at FROM approval_votes WHERE token = ? ORDER BY at ASC",
            (r["token"],),
        )
        votes = [dict(v) for v in await vcur.fetchall()]
        out.append(
            {
                "token": r["token"],
                "case_id": r["case_id"],
                "action": r["action"],
                "required": r["required"],
                "status": r["status"],
                "requested_by": r["requested_by"],
                "created_at": r["created_at"],
                "due_at": r["due_at"],
                "evidence": json.loads(r["evidence_json"] or "{}"),
                "votes": votes,
                "approve_count": sum(1 for v in votes if v["decision"] == "approved"),
            }
        )
    return out


async def get_approval(db: aiosqlite.Connection, token: str) -> dict[str, Any] | None:
    items = await list_approvals(db, status="pending")
    for item in items:
        if item["token"] == token:
            return item
    cur = await db.execute("SELECT * FROM approvals WHERE token = ?", (token,))
    r = await cur.fetchone()
    if not r:
        return None
    vcur = await db.execute(
        "SELECT user_id, decision, reason, at FROM approval_votes WHERE token = ? ORDER BY at ASC",
        (token,),
    )
    votes = [dict(v) for v in await vcur.fetchall()]
    return {
        "token": r["token"],
        "case_id": r["case_id"],
        "action": r["action"],
        "required": r["required"],
        "status": r["status"],
        "requested_by": r["requested_by"],
        "evidence": json.loads(r["evidence_json"] or "{}"),
        "votes": votes,
        "approve_count": sum(1 for v in votes if v["decision"] == "approved"),
    }


async def sweep_timeouts(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    now = demo_clock.now()
    cur = await db.execute(
        "SELECT * FROM approvals WHERE status = 'pending' AND due_at <= ?", (now,)
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
        (qid, case_id, kind, urgency, title, detail, ladder_step, demo_clock.now()),
    )
    await db.commit()
    return qid


async def list_queue(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    cur = await db.execute(
        "SELECT * FROM queue_items WHERE status = 'open' ORDER BY created_at ASC"
    )
    return [dict(r) for r in await cur.fetchall()]
