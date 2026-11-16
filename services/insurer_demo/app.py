"""Standalone Demo Health Insurance A2A stub (#107).

Run from repo root:
  PYTHONPATH=services/orchestrator uvicorn services.insurer_demo.app:app --port 8101
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

_SERVICES = Path(__file__).resolve().parents[1]
for _p in (_SERVICES / "orchestrator", _SERVICES):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.insurer import SCENARIOS, agent_card, check_coverage, payment_options, submit_claim

app = FastAPI(title="Demo Health Insurance", version="0.1.0")


class Query(BaseModel):
    plan_id: str = "plan-a"
    provider_id: str = "prov-1"
    consent_insurer_query: bool = True
    scenario: str | None = None


@app.get("/.well-known/agent.json")
def card():
    return agent_card()


@app.post("/a2a/eligibility")
@app.post("/a2a/preauth")
@app.post("/a2a/cost")
def exchange(body: Query):
    if body.scenario and body.scenario in SCENARIOS:
        return SCENARIOS[body.scenario]
    return check_coverage(
        plan_id=body.plan_id, provider_id=body.provider_id, consent=body.consent_insurer_query
    )


@app.post("/a2a/payment-options")
def payment(body: Query):
    return payment_options(plan_id=body.plan_id, provider_id=body.provider_id, consent=body.consent_insurer_query)


class ClaimIn(BaseModel):
    case_id: str
    plan_id: str
    provider_id: str
    amount_aed: int = 0
    consent_insurer_query: bool = True


@app.post("/a2a/claims")
def claims(body: ClaimIn):
    return submit_claim(
        case_id=body.case_id,
        plan_id=body.plan_id,
        provider_id=body.provider_id,
        amount_aed=body.amount_aed,
        consent=body.consent_insurer_query,
    )
