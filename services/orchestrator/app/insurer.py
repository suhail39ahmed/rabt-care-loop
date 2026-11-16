"""Mock insurer A2A connector — Demo Health Insurance (#74–#77, #107)."""

from __future__ import annotations

from typing import Any

# Allowlisted response fields only — never execute free text as instructions (#76).
ALLOWED_FIELDS = frozenset(
    {
        "status",
        "covered",
        "preauth_required",
        "preauth_status",
        "patient_cost_aed",
        "plan_name",
        "reason_code",
        "scenario",
        # payment-path skill
        "cashless_available",
        "reimbursement_available",
        "reimbursement_pct",
        "claim_window_days",
        "required_documents",
        # claim skill
        "claim_reference",
        "claim_status",
        "decision_days",
    }
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
        "skills": ["eligibility", "preauth", "cost", "payment_options", "claim_submit"],
        "authentication": "demo",
    }


def _sanitize(raw: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in raw.items() if k in ALLOWED_FIELDS}


def check_coverage(*, plan_id: str, provider_id: str, consent: bool) -> dict[str, Any]:
    if not consent:
        return {"status": "error", "reason_code": "CONSENT_REQUIRED", "covered": False}
    # Deterministic scenario pick for demo.
    # Preauth is opt-in (plan/provider name), not all of Plan B — otherwise golden
    # and closure tests that book Fatima/Omar (plan-b) fail at seed/book.
    if "self" in (plan_id or "") or provider_id.endswith("-oon"):
        key = "oon"
    elif "deny" in (provider_id or ""):
        key = "denied"
    elif "preauth" in (plan_id or "") or provider_id.endswith("-preauth"):
        key = "preauth"
    else:
        key = "covered"
    return _sanitize(SCENARIOS[key])


def payment_options(*, plan_id: str, provider_id: str, consent: bool) -> dict[str, Any]:
    """A2A skill: can this visit be cashless, or does the plan reimburse pay-and-claim?"""
    if not consent:
        return {"status": "error", "reason_code": "CONSENT_REQUIRED"}
    from agents.navigator.payment import REQUIRED_DOCUMENTS

    from app.reference_data import PLANS, PROVIDERS

    plan = PLANS.get(plan_id)
    provider = next((p for p in PROVIDERS if p["id"] == provider_id), None)
    if plan is None or provider is None:
        return _sanitize({"status": "error", "reason_code": "UNKNOWN_PLAN_OR_PROVIDER"})
    in_network = provider.get("network_id") == plan["network_id"]
    reimb = plan.get("reimbursement") or {}
    cashless = in_network and bool(provider.get("cashless", True)) and bool(plan.get("cashless", True))
    reimb_ok = (not cashless) and bool(reimb.get("in_network" if in_network else "out_of_network"))
    return _sanitize(
        {
            "status": "ok",
            "plan_name": plan["name"],
            "cashless_available": cashless,
            "reimbursement_available": reimb_ok,
            "reimbursement_pct": int(reimb.get("pct", 0)) if reimb_ok else 0,
            "claim_window_days": int(reimb.get("claim_window_days", 0)) if reimb_ok else None,
            "required_documents": [d["id"] for d in REQUIRED_DOCUMENTS] if reimb_ok else [],
            "reason_code": "CASHLESS" if cashless else ("REIMBURSABLE" if reimb_ok else "NOT_COVERED"),
        }
    )


def submit_claim(*, case_id: str, plan_id: str, provider_id: str, amount_aed: int, consent: bool) -> dict[str, Any]:
    """A2A skill: accept a reimbursement claim and return a reference (no decision yet)."""
    if not consent:
        return {"status": "error", "reason_code": "CONSENT_REQUIRED"}
    import hashlib

    ref = hashlib.sha256(f"{case_id}|{plan_id}|{provider_id}|{amount_aed}".encode()).hexdigest()[:8].upper()
    return _sanitize(
        {
            "status": "ok",
            "claim_reference": f"DHI-CLM-{ref}",
            "claim_status": "received",
            "decision_days": 5,
            "reason_code": "CLAIM_RECEIVED",
        }
    )
