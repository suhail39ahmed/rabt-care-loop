"""Standalone Demo Health Insurance A2A stub (#107).

Run from repo root:
  PYTHONPATH=services/orchestrator uvicorn services.insurer_demo.app:app --port 8101
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

_ORCH = Path(__file__).resolve().parents[1] / "orchestrator"
if str(_ORCH) not in sys.path:
    sys.path.insert(0, str(_ORCH))

from app.insurer import SCENARIOS, agent_card, check_coverage

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
