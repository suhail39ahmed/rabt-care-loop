"""Demo auth — persona header for writes; ingest secret for webhooks."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable

from fastapi import Header, HTTPException, Request

# Canonical demo personas → role. Aliases collapsed so one human cannot vote twice.
PERSONA_ROLES: dict[str, str] = {
    "human:coordinator-sara": "coordinator",
    "human:gp-aisha": "physician",
    "human:gp-khan": "physician",
    "human:supervisor": "supervisor",
    "patient:fatima": "patient",
}

# Legacy ids accepted on the wire, rewritten to a canonical persona.
PERSONA_ALIASES: dict[str, str] = {
    "human:gp": "human:gp-aisha",
    "human:coordinator": "human:coordinator-sara",
}

DEMO_PERSONAS = set(PERSONA_ROLES) | set(PERSONA_ALIASES)

CLINICIAN_ROLES = frozenset({"physician", "coordinator", "supervisor"})
PATIENT_ROUTES = frozenset({"teachback", "book", "reassure", "consent", "concern", "claim"})
CLINICIAN_ONLY_SUFFIXES = (
    "/accept",
    "/decline",
    "/attend",
    "/outcome",
    "/close",
    "/escalation/handle",
    "/reject-referral",
    "/econsult",
    "/notify",
    "/call/outcome",
    "/unreachable",
    "/callback/done",
    "/data-query/resolve",
    "/consent/resume",
)


def canonical_persona(persona: str) -> str:
    return PERSONA_ALIASES.get(persona, persona)


def role_for(persona: str) -> str | None:
    return PERSONA_ROLES.get(canonical_persona(persona))


def as_actor(persona: str) -> str:
    """Record actors as human:<id> / patient:<id> without double prefixes."""
    p = canonical_persona(persona or "")
    if p.startswith(("human:", "patient:", "system:", "agent:")):
        return p
    if p:
        return f"human:{p}"
    return "human:unknown"


def ingest_secret_ok(provided: str | None) -> bool:
    expected = os.environ.get("RABT_INGEST_SECRET", "").strip()
    if not expected:
        # Local/dev without secret: allow (documented limitation)
        return True
    return bool(provided) and provided == expected


def persona_allowed(persona: str | None) -> bool:
    return bool(persona) and persona in DEMO_PERSONAS


def write_role_allowed(path: str, role: str) -> bool:
    """Per-route demo role rules (#52)."""
    if path.startswith("/demo/"):
        return role in CLINICIAN_ROLES
    if path == "/translate":
        return True
    if path.startswith("/approvals/") and path.endswith("/decision"):
        return role in CLINICIAN_ROLES
    if "/consent/withdraw" in path:
        return role == "patient" or role in CLINICIAN_ROLES
    m = re.search(r"/cases/[^/]+/([^/]+)", path)
    if m:
        action = m.group(1)
        if action in PATIENT_ROUTES:
            return role == "patient" or role in CLINICIAN_ROLES
        if any(path.endswith(suf) for suf in CLINICIAN_ONLY_SUFFIXES):
            return role in CLINICIAN_ROLES
        # Unknown case write: clinicians only
        return role in CLINICIAN_ROLES
    # Other writes (ingest uses secret; leftover paths)
    return role in CLINICIAN_ROLES


def require_roles(role: str, allowed: Iterable[str]) -> None:
    if role not in set(allowed):
        raise HTTPException(403, f"persona role '{role}' not allowed for this action")


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
    if persona not in DEMO_PERSONAS:
        raise HTTPException(403, f"unknown demo persona: {persona}")
    return canonical_persona(persona)


async def require_ingest_secret(
    x_rabt_ingest_secret: str | None = Header(default=None, alias="X-Rabt-Ingest-Secret"),
) -> None:
    if not ingest_secret_ok(x_rabt_ingest_secret):
        raise HTTPException(401, "invalid or missing X-Rabt-Ingest-Secret")
