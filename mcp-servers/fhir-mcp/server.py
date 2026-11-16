"""Scoped FHIR MCP tool server (stdlib + httpx / memory bridge)."""

from __future__ import annotations

import os

import httpx
from mcp.server.fastmcp import FastMCP

FHIR = os.environ.get("FHIR_BASE_URL", "http://localhost:8080/fhir")
ORCH = os.environ.get("ORCH_BASE_URL", "http://localhost:8000")
mcp = FastMCP("rabt-fhir")

ALLOWED_BUSINESS_STATES = {
    "New",
    "DataQuery",
    "Triaged",
    "Escalated",
    "AwaitingOwner",
    "Owned",
    "PatientNotified",
    "Unreachable",
    "HumanCallback",
    "Understood",
    "Referred",
    "ReferralRejected",
    "Booked",
    "NoShow",
    "Attended",
    "ClosurePending",
    "Closed",
    "Transferred",
    "OnHoldConsent",
    "ClosedByHuman",
}


def _scope(step: str, tool: str) -> None:
    """Enforce the same tool scopes as the orchestrator (prototype)."""
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "services" / "orchestrator"))
    from app.tools import assert_tool_allowed

    assert_tool_allowed(step, tool)


@mcp.tool()
async def read_case_bundle(task_id: str) -> dict:
    """Return minimal case fields from the Rabt orchestrator (prototype bridge)."""
    _scope("triage", "read_case_bundle")
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{ORCH}/cases/{task_id}")
        if r.status_code == 404:
            return {"ok": False, "error": "not found"}
        r.raise_for_status()
        case = r.json()
        return {
            "ok": True,
            "task_id": task_id,
            "state": case.get("state"),
            "urgency": case.get("urgency"),
            "patient_id": case.get("patient_id"),
            "language": case.get("language"),
            "result_display": case.get("result_display"),
            "owner_id": case.get("owner_id"),
        }


@mcp.tool()
async def update_task_state(task_id: str, business_state: str, fhir_status: str, reason: str) -> dict:
    """Validate business state; prototype logs intent (state changes go through orchestrator API)."""
    _scope("ownership", "update_task_state")
    if business_state not in ALLOWED_BUSINESS_STATES:
        return {"ok": False, "error": f"unknown state {business_state}"}
    return {
        "ok": True,
        "task_id": task_id,
        "business_state": business_state,
        "fhir_status": fhir_status,
        "reason": reason,
        "note": "Prototype: apply transitions via orchestrator HTTP API for safety.",
    }


@mcp.tool()
async def write_communication(task_id: str, patient_id: str, language: str, text: str, channel: str) -> dict:
    """Record a communication intent (console channel in prototype)."""
    _scope("comms", "write_communication")
    print(f"[messaging:{channel}] case={task_id} patient={patient_id} lang={language}: {text[:120]}")
    return {"ok": True, "status": "completed", "channel": channel}


if __name__ == "__main__":
    mcp.run()
