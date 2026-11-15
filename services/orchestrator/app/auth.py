"""Demo auth — persona header for writes; ingest secret for webhooks."""

from __future__ import annotations

import os

from fastapi import Header, HTTPException, Request

DEMO_PERSONAS = {
    "human:coordinator-sara",
    "human:gp-aisha",
    "human:supervisor",
    "human:gp",
    "human:gp-khan",
    "human:coordinator",
    "patient:fatima",
}


def ingest_secret_ok(provided: str | None) -> bool:
    expected = os.environ.get("RABT_INGEST_SECRET", "").strip()
    if not expected:
        # Local/dev without secret: allow (documented limitation)
        return True
    return bool(provided) and provided == expected


async def require_persona(
    request: Request,
    x_rabt_persona: str | None = Header(default=None, alias="X-Rabt-Persona"),
) -> str:
    """Write routes require a demo persona header (set by the board switcher)."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return x_rabt_persona or "guest"
    persona = x_rabt_persona or ""
    if not persona:
        raise HTTPException(401, "X-Rabt-Persona header required for write routes")
    if persona not in DEMO_PERSONAS and not persona.startswith(("human:", "patient:")):
        raise HTTPException(403, f"unknown demo persona: {persona}")
    return persona


async def require_ingest_secret(
    x_rabt_ingest_secret: str | None = Header(default=None, alias="X-Rabt-Ingest-Secret"),
) -> None:
    if not ingest_secret_ok(x_rabt_ingest_secret):
        raise HTTPException(401, "invalid or missing X-Rabt-Ingest-Secret")
