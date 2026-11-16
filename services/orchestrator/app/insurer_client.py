"""Calls the insurer agent over A2A and returns only validated data.

- INSURER_A2A_URL set: signed HTTP to the separate insurer agent (its own container app). The reply
  must carry a valid insurer signature, then passes the strict schema in agents.common.a2a.
- Not set (local dev, tests): the in-process demo insurer, through the same schema validation.

Every exchange is recorded (request fields, transport, verification, dropped fields) for the case
timeline and the insurer page. A rejected or unreachable reply never reaches the navigator: it
becomes status=error with INSURER_REPLY_REJECTED / INSURER_UNAVAILABLE and goes to a human.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import deque
from typing import Any

import httpx
from agents.common.a2a import (
    INSURER_AGENT,
    ORCHESTRATOR_AGENT,
    A2AError,
    sign_headers,
    validate_reply,
    verify,
)

log = logging.getLogger("rabt.a2a")
EXCHANGES: deque[dict[str, Any]] = deque(maxlen=50)


def insurer_url() -> str:
    return os.getenv("INSURER_A2A_URL", "").rstrip("/")


def _timeout() -> float:
    return float(os.getenv("INSURER_A2A_TIMEOUT_S", "5"))


def _new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=_timeout())


def _in_process(skill: str, payload: dict[str, Any]) -> dict[str, Any]:
    from app import insurer

    consent = bool(payload.get("consent_insurer_query", True))
    if skill == "eligibility":
        return insurer.check_coverage(plan_id=payload["plan_id"], provider_id=payload["provider_id"], consent=consent)
    if skill == "payment-options":
        return insurer.payment_options(plan_id=payload["plan_id"], provider_id=payload["provider_id"], consent=consent)
    return insurer.submit_claim(
        case_id=payload["case_id"],
        plan_id=payload["plan_id"],
        provider_id=payload["provider_id"],
        amount_aed=int(payload.get("amount_aed") or 0),
        consent=consent,
    )


async def _over_http(skill: str, payload: dict[str, Any], client: httpx.AsyncClient | None) -> tuple[Any, bool]:
    path = f"/a2a/{skill}"
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    headers = {"content-type": "application/json", **sign_headers(ORCHESTRATOR_AGENT, "POST", path, body)}
    own = client is None
    client = client or _new_client()
    try:
        r = await client.post(insurer_url() + path, content=body, headers=headers)
    finally:
        if own:
            await client.aclose()
    r.raise_for_status()
    verify(r.headers, "REPLY", path, r.content, expected_agent=INSURER_AGENT)
    return r.json(), True


async def call_insurer(
    skill: str, payload: dict[str, Any], *, case: str | None = None, client: httpx.AsyncClient | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Returns (validated reply, exchange record)."""
    started = time.time()
    transport = "http" if insurer_url() else "in-process"
    record: dict[str, Any] = {
        "at": int(started),
        "case_id": case,
        "skill": skill,
        "transport": transport,
        "request_fields": sorted(payload),
        "signature_verified": False,
        "dropped_fields": [],
    }
    try:
        if transport == "http":
            raw, record["signature_verified"] = await _over_http(skill, payload, client)
        else:
            raw = _in_process(skill, payload)
        reply, dropped = validate_reply(skill, raw)
        record.update(outcome="accepted", dropped_fields=dropped, reason_code=reply.get("reason_code"))
    except A2AError as e:
        reply = {"status": "error", "reason_code": "INSURER_REPLY_REJECTED"}
        record.update(outcome="rejected", error=str(e)[:200], reason_code="INSURER_REPLY_REJECTED")
        log.warning("a2a reply rejected skill=%s err=%s", skill, e)
    except (httpx.HTTPError, ValueError) as e:
        reply = {"status": "error", "reason_code": "INSURER_UNAVAILABLE"}
        record.update(outcome="unavailable", error=type(e).__name__, reason_code="INSURER_UNAVAILABLE")
        log.warning("a2a insurer unavailable skill=%s err=%s", skill, type(e).__name__)
    record["ms"] = int((time.time() - started) * 1000)
    EXCHANGES.appendleft(record)
    try:
        from agents.common import ai_metrics

        ai_metrics.incr(f"a2a_{record['outcome']}")
    except Exception:  # pragma: no cover - metrics never break the flow
        pass
    return reply, record
