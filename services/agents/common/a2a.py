"""Signed agent-to-agent (A2A) messages and strict validation of untrusted replies.

Every A2A request and reply carries:
  X-Rabt-Agent      caller / responder identity (e.g. "rabt-orchestrator", "demo-health-insurance")
  X-Rabt-Timestamp  unix seconds; rejected outside A2A_MAX_SKEW_S (default 300)
  X-Rabt-Signature  hex HMAC-SHA256 over "<agent>.<timestamp>.<method>.<path>.<body>" with A2A_SHARED_SECRET

Replies from another agent are data, never instructions: they are parsed into a strict schema
(unknown fields dropped, types and ranges enforced, free text PII-scrubbed and injection-checked).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

ORCHESTRATOR_AGENT = "rabt-orchestrator"
INSURER_AGENT = "demo-health-insurance"
_REASON = re.compile(r"^[A-Z][A-Z_]{1,39}$")


class A2AError(Exception):
    """Signature, freshness or schema failure: the message is not trusted."""


def shared_secret() -> str:
    return os.getenv("A2A_SHARED_SECRET", "")


def _max_skew() -> int:
    return int(os.getenv("A2A_MAX_SKEW_S", "300"))


def signature(secret: str, agent: str, ts: str, method: str, path: str, body: bytes) -> str:
    msg = b".".join([agent.encode(), ts.encode(), method.upper().encode(), path.encode(), body])
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def sign_headers(agent: str, method: str, path: str, body: bytes, *, secret: str | None = None, now: float | None = None) -> dict[str, str]:
    secret = shared_secret() if secret is None else secret
    if not secret:
        raise A2AError("A2A_SHARED_SECRET is not set")
    ts = str(int(now if now is not None else time.time()))
    return {
        "X-Rabt-Agent": agent,
        "X-Rabt-Timestamp": ts,
        "X-Rabt-Signature": signature(secret, agent, ts, method, path, body),
    }


def verify(
    headers: Any,
    method: str,
    path: str,
    body: bytes,
    *,
    expected_agent: str,
    secret: str | None = None,
    now: float | None = None,
) -> None:
    """Raise A2AError unless the message is signed by `expected_agent` with the shared secret and is fresh."""
    secret = shared_secret() if secret is None else secret
    if not secret:
        raise A2AError("A2A_SHARED_SECRET is not set")
    agent = headers.get("X-Rabt-Agent") or headers.get("x-rabt-agent") or ""
    ts = headers.get("X-Rabt-Timestamp") or headers.get("x-rabt-timestamp") or ""
    sig = headers.get("X-Rabt-Signature") or headers.get("x-rabt-signature") or ""
    if agent != expected_agent:
        raise A2AError(f"unexpected agent {agent!r}")
    if not ts.isdigit() or abs((now if now is not None else time.time()) - int(ts)) > _max_skew():
        raise A2AError("stale or missing timestamp")
    if not hmac.compare_digest(sig, signature(secret, agent, ts, method, path, body)):
        raise A2AError("bad signature")


# --------------------------------------------------------------------------- reply schemas


class _Reply(BaseModel):
    model_config = ConfigDict(extra="ignore", str_max_length=200)

    status: Literal["ok", "error"]
    reason_code: str = "UNKNOWN"
    plan_name: str | None = Field(default=None, max_length=80)

    @field_validator("reason_code")
    @classmethod
    def _reason(cls, v: str) -> str:
        if not _REASON.match(v):
            raise ValueError("reason_code must be an upper-case code")
        return v

    @field_validator("plan_name")
    @classmethod
    def _plan_name(cls, v: str | None) -> str | None:
        return None if v is None else clean_free_text(v)


class CoverageReply(_Reply):
    covered: bool = False
    preauth_required: bool = False
    preauth_status: Literal["not_required", "pending", "approved", "denied", "n/a"] = "n/a"
    patient_cost_aed: int | None = Field(default=None, ge=0, le=100_000)
    scenario: Literal["covered", "preauth", "oon", "denied"] | None = None


class PaymentOptionsReply(_Reply):
    cashless_available: bool = False
    reimbursement_available: bool = False
    reimbursement_pct: int = Field(default=0, ge=0, le=100)
    claim_window_days: int | None = Field(default=None, ge=0, le=365)
    required_documents: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("required_documents")
    @classmethod
    def _docs(cls, v: list[str]) -> list[str]:
        from agents.navigator.payment import REQUIRED_DOCUMENTS

        known = {d["id"] for d in REQUIRED_DOCUMENTS}
        return [d for d in v if d in known]


class ClaimAck(_Reply):
    claim_reference: str | None = Field(default=None, pattern=r"^[A-Z0-9-]{4,40}$")
    claim_status: Literal["received", "in_review", "approved", "rejected"] | None = None
    decision_days: int | None = Field(default=None, ge=0, le=90)


REPLY_SCHEMAS: dict[str, type[_Reply]] = {
    "eligibility": CoverageReply,
    "payment-options": PaymentOptionsReply,
    "claims": ClaimAck,
}


def clean_free_text(text: str) -> str:
    """Free text from another agent: PII-scrubbed and refused if it carries instructions."""
    from agents.common.injection import deny_listed
    from agents.common.pii import scrub

    if deny_listed(text):
        raise ValueError("instruction-like text in an A2A field")
    return scrub(text).text


def validate_reply(skill: str, raw: Any) -> tuple[dict[str, Any], list[str]]:
    """Parse an untrusted reply. Returns (clean dict, dropped field names). Raises A2AError when invalid."""
    schema = REPLY_SCHEMAS[skill]
    if not isinstance(raw, dict):
        raise A2AError("reply is not a JSON object")
    dropped = sorted(k for k in raw if k not in schema.model_fields)
    try:
        model = schema.model_validate(raw)
    except ValidationError as e:
        raise A2AError(f"reply failed schema: {e.errors()[0].get('msg', 'invalid')}") from e
    return model.model_dump(exclude_none=False), dropped
