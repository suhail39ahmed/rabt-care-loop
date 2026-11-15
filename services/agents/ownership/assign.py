"""Ownership assignment + SLA placeholders."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

# Illustrative placeholders — not ADPHC-approved SLAs
SLA_HOURS = {
    "CRITICAL": 1,
    "URGENT": 48,
    "ROUTINE": 168,
    "NEEDS_HUMAN": 24,
}


def assign_owner(patient: dict[str, Any], urgency: str) -> dict[str, Any]:
    gp = patient.get("generalPractitioner") or []
    if gp:
        ref = gp[0].get("reference", "Practitioner/gp-demo")
        name = gp[0].get("display", "Dr Aisha (Family Physician)")
    else:
        ref = "Practitioner/coordinator-mariam"
        name = "Mariam (Screening Coordinator)"
    due = datetime.now(timezone.utc) + timedelta(hours=SLA_HOURS.get(urgency, 48))
    return {
        "owner_id": ref,
        "owner_name": name,
        "due_at": due.isoformat(),
        "sla_hours": SLA_HOURS.get(urgency, 48),
    }


async def run(req: dict[str, Any]) -> dict[str, Any]:
    inputs = req.get("inputs", {})
    patient = inputs.get("patient") or {}
    urgency = inputs.get("urgency") or "ROUTINE"
    assignment = assign_owner(patient, urgency)
    return {
        "case_id": req["case_id"],
        "step": "ownership",
        "status": "ok",
        "proposed_transition": "AwaitingOwner",
        "outputs": assignment,
        "evidence_refs": [assignment["owner_id"]],
    }
