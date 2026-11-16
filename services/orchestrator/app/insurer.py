"""Mock insurer A2A connector — Demo Health Insurance (#74–#77, #107)."""

from __future__ import annotations

from typing import Any

# Allowlisted response fields only — never execute free text as instructions (#76).
ALLOWED_FIELDS = frozenset(
    {"status", "covered", "preauth_required", "preauth_status", "patient_cost_aed", "plan_name", "reason_code", "scenario"}
)

SCENARIOS: dict[str, dict[str, Any]] = {
    "covered": {
        "status": "ok",
        "covered": True,
        "preauth_required": False,
        "preauth_status": "not_required",
        "patient_cost_aed": 0,
        "plan_name": "Demo Health Insurance Gold",
        "reason_code": "IN_NETWORK",
        "scenario": "covered",
    },
    "preauth": {
        "status": "ok",
        "covered": True,
        "preauth_required": True,
        "preauth_status": "pending",
        "patient_cost_aed": 50,
        "plan_name": "Demo Health Insurance Silver",
        "reason_code": "PREAUTH_REQUIRED",
        "scenario": "preauth",
    },
    "oon": {
        "status": "ok",
        "covered": False,
        "preauth_required": False,
        "preauth_status": "n/a",
        "patient_cost_aed": 350,
        "plan_name": "Demo Health Insurance",
        "reason_code": "OUT_OF_NETWORK",
        "scenario": "oon",
    },
    "denied": {
        "status": "ok",
        "covered": False,
        "preauth_required": False,
        "preauth_status": "denied",
        "patient_cost_aed": None,
        "plan_name": "Demo Health Insurance",
        "reason_code": "DENIED",
        "scenario": "denied",
    },
}


def agent_card() -> dict[str, Any]:
    return {
        "name": "Demo Health Insurance",
        "description": "Synthetic A2A insurer for Rabt demo — not a real payer.",
        "url": "in-process://demo-health-insurance",
        "skills": ["eligibility", "preauth", "cost"],
        "authentication": "demo",
    }


def _sanitize(raw: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in raw.items() if k in ALLOWED_FIELDS}


def check_coverage(*, plan_id: str, provider_id: str, consent: bool) -> dict[str, Any]:
    if not consent:
        return {"status": "error", "reason_code": "CONSENT_REQUIRED", "covered": False}
    # Deterministic scenario pick for demo
    if "self" in (plan_id or "") or provider_id.endswith("-oon"):
        key = "oon"
    elif (plan_id or "").endswith("-b"):
        key = "preauth"
    elif "deny" in (provider_id or ""):
        key = "denied"
    else:
        key = "covered"
    return _sanitize(SCENARIOS[key])
