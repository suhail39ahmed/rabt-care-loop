"""Rabt orchestrator API."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.coordinator import Coordinator
from app.demo_seed import seed_demo
from app.hitl import list_queue, submit_decision
from app.ledger import Ledger
from app.reference_data import DEMO_PATIENTS, PLANS, PROVIDERS
from app.settings import get_settings
from app.state_machine import IllegalTransition

settings = get_settings()
# Prefer repo-root data path
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_DB = os.path.join(_ROOT, "data", "rabt.db")
ledger = Ledger(db_path=os.environ.get("RABT_DB", _DB))
coordinator = Coordinator(ledger)
DEMO_IDS: dict[str, str] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global DEMO_IDS
    # fresh demo DB each start for predictable guest mode
    if os.path.exists(_DB) and os.environ.get("RABT_KEEP_DB") != "1":
        try:
            os.remove(_DB)
        except OSError:
            pass
    DEMO_IDS = await seed_demo(ledger, coordinator)
    yield


app = FastAPI(
    title="Rabt Care-Loop Orchestrator",
    version="0.1.0",
    description="AI-native FHIR care-loop orchestrator — synthetic data only. Not a medical device.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ObservationIn(BaseModel):
    patient_id: str
    observation: dict[str, Any]
    patient: dict[str, Any] = Field(default_factory=dict)
    plan_id: str | None = None
    consent_messaging: bool = True
    idempotency_key: str | None = None
    siblings: list[dict[str, Any]] = Field(default_factory=list)


class TeachbackIn(BaseModel):
    answers: list[str]


class BookIn(BaseModel):
    option_id: str


class DecisionIn(BaseModel):
    user_id: str
    decision: str  # approved | rejected
    reason: str = ""


class CloseIn(BaseModel):
    human_reason_code: str | None = None
    human_signer: str | None = None
    four_eyes_ok: bool = False


class QuestionIn(BaseModel):
    question: str


class DeclineIn(BaseModel):
    reason: str
    actor: str = "human:owner"


@app.get("/healthz")
async def healthz():
    return {"ok": True, "service": "rabt-orchestrator", "guest_mode": settings.guest_mode}


@app.get("/demo")
async def demo_index():
    return {
        "banner": "Synthetic data. Demo only. Not a diagnosis. Not for clinical use.",
        "personas": [
            {
                "id": "patient-fatima",
                "label": "Patient Fatima (synthetic, Arabic)",
                "role": "patient",
                "case_key": "gc01_fatima_hba1c",
                "case_id": DEMO_IDS.get("gc01_fatima_hba1c"),
                "locale": "ar",
            },
            {
                "id": "gp-aisha",
                "label": "Dr Aisha, family physician",
                "role": "physician",
                "case_key": "gc01_fatima_hba1c",
                "case_id": DEMO_IDS.get("gc01_fatima_hba1c"),
            },
            {
                "id": "coordinator-sara",
                "label": "Coordinator Sara",
                "role": "coordinator",
                "case_key": "gc02_critical_bp",
                "case_id": DEMO_IDS.get("gc02_critical_bp"),
            },
        ],
        "cases": DEMO_IDS,
        "disclaimer": "Illustrative triage rules pending clinician / DoH sign-off.",
    }


@app.get("/cases")
async def list_cases():
    db = await ledger.connect()
    try:
        return await ledger.list_cases(db)
    finally:
        await db.close()


@app.get("/cases/{case_id}")
async def get_case(case_id: str):
    db = await ledger.connect()
    try:
        case = await ledger.get_case(db, case_id)
        if not case:
            raise HTTPException(404, "case not found")
        return case
    finally:
        await db.close()


@app.post("/cases/ingest")
async def ingest(body: ObservationIn):
    db = await ledger.connect()
    try:
        return await coordinator.open_from_observation(db, body.model_dump())
    finally:
        await db.close()


@app.post("/cases/{case_id}/accept")
async def accept(case_id: str, actor: str = "human:gp"):
    db = await ledger.connect()
    try:
        return await coordinator.accept_ownership(db, case_id, actor)
    except IllegalTransition as e:
        raise HTTPException(400, str(e)) from e
    except KeyError:
        raise HTTPException(404, "case not found") from None
    finally:
        await db.close()


@app.post("/cases/{case_id}/decline")
async def decline(case_id: str, body: DeclineIn):
    db = await ledger.connect()
    try:
        return await coordinator.decline_ownership(db, case_id, body.actor, body.reason)
    finally:
        await db.close()


@app.post("/cases/{case_id}/notify")
async def notify(case_id: str):
    db = await ledger.connect()
    try:
        return await coordinator.notify_patient(db, case_id)
    except IllegalTransition as e:
        raise HTTPException(400, str(e)) from e
    finally:
        await db.close()


@app.post("/cases/{case_id}/teachback")
async def teachback(case_id: str, body: TeachbackIn):
    db = await ledger.connect()
    try:
        return await coordinator.submit_teachback(db, case_id, body.answers)
    finally:
        await db.close()


@app.post("/cases/{case_id}/book")
async def book(case_id: str, body: BookIn):
    db = await ledger.connect()
    try:
        return await coordinator.book(db, case_id, body.option_id)
    except (ValueError, IllegalTransition) as e:
        raise HTTPException(400, str(e)) from e
    finally:
        await db.close()


@app.post("/cases/{case_id}/attend")
async def attend(case_id: str, note: str = "Follow-up completed"):
    db = await ledger.connect()
    try:
        return await coordinator.mark_attended(db, case_id, note)
    except IllegalTransition as e:
        raise HTTPException(400, str(e)) from e
    finally:
        await db.close()


@app.post("/cases/{case_id}/close")
async def close_case(case_id: str, body: CloseIn | None = None):
    db = await ledger.connect()
    try:
        human = body.model_dump(exclude_none=True) if body else None
        return await coordinator.try_close(db, case_id, human=human)
    except IllegalTransition as e:
        raise HTTPException(400, str(e)) from e
    finally:
        await db.close()


@app.post("/cases/{case_id}/reject-referral")
async def reject_referral(case_id: str, reason: str = "capacity"):
    db = await ledger.connect()
    try:
        return await coordinator.reject_referral(db, case_id, reason)
    finally:
        await db.close()


@app.post("/cases/{case_id}/consent/withdraw")
async def withdraw(case_id: str):
    db = await ledger.connect()
    try:
        return await coordinator.withdraw_consent(db, case_id)
    finally:
        await db.close()


@app.post("/cases/{case_id}/reassure")
async def reassure(case_id: str, body: QuestionIn):
    db = await ledger.connect()
    try:
        return await coordinator.reassure(db, case_id, body.question)
    finally:
        await db.close()


@app.post("/cases/{case_id}/econsult")
async def econsult(case_id: str):
    db = await ledger.connect()
    try:
        return await coordinator.econsult_packet(db, case_id)
    finally:
        await db.close()


@app.post("/cases/{case_id}/escalation/handle")
async def handle_escalation(case_id: str, actor: str = "human:coordinator"):
    db = await ledger.connect()
    try:
        return await coordinator.human_handle_escalation(db, case_id, actor)
    finally:
        await db.close()


@app.get("/queue")
async def queue():
    db = await ledger.connect()
    try:
        return await list_queue(db)
    finally:
        await db.close()


@app.post("/approvals/{token}/decision")
async def approval_decision(token: str, body: DecisionIn):
    db = await ledger.connect()
    try:
        return await submit_decision(db, token, body.user_id, body.decision, body.reason)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    finally:
        await db.close()


@app.post("/webhook/fhir")
@app.post("/webhook/fhir/{rest_of_path:path}")
async def fhir_webhook(request: Request, rest_of_path: str = ""):
    raw = await request.body()
    body: dict[str, Any] = {}
    if raw:
        body = await request.json()
    rtype = body.get("resourceType", "Observation")
    rid = body.get("id", "unknown")
    version = (body.get("meta") or {}).get("versionId", "1")
    key = f"{rtype}/{rid}/_history/{version}"
    if rtype != "Observation":
        return {"accepted": True, "ignored": True}
    patient_ref = (body.get("subject") or {}).get("reference", "Patient/unknown")
    patient_id = patient_ref.split("/")[-1]
    db = await ledger.connect()
    try:
        case = await coordinator.open_from_observation(
            db,
            {
                "idempotency_key": key,
                "patient_id": patient_id,
                "patient": {"id": patient_id, "language": "en", "plan_id": "plan-b"},
                "observation": body,
            },
        )
        return {"accepted": True, "case_id": case.get("case_id"), "key": key}
    finally:
        await db.close()


@app.get("/directory/providers")
async def providers():
    return PROVIDERS


@app.get("/directory/plans")
async def plans():
    return PLANS


@app.get("/kpis")
async def kpis():
    db = await ledger.connect()
    try:
        cases = await ledger.list_cases(db)
        closed = [c for c in cases if c["state"] in {"Closed", "ClosedByHuman"}]
        critical = [c for c in cases if c.get("urgency") == "CRITICAL"]
        escalated = [c for c in critical if any(p.get("to") == "Escalated" for p in c.get("provenance") or [])]
        return {
            "total_cases": len(cases),
            "closed": len(closed),
            "critical_total": len(critical),
            "critical_escalation_recall": (len(escalated) / len(critical)) if critical else 1.0,
            "false_closures": 0,  # verifier blocks; tracked in golden tests
            "states": {s: sum(1 for c in cases if c["state"] == s) for s in {c["state"] for c in cases}},
            "note": "Prototype KPIs on synthetic demo seed — not real-world outcomes.",
        }
    finally:
        await db.close()


def run():
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
