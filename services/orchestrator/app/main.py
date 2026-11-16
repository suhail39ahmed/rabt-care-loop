"""Rabt orchestrator API."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from app import demo_clock
from app.auth import ingest_secret_ok, persona_allowed
from app.coordinator import Coordinator
from app.demo_seed import seed_demo
from app.hitl import ApprovalError, list_approvals, list_queue, mark_approved, submit_decision
from app.ledger import Ledger
from app.reference_data import PLANS, PROVIDERS
from app.settings import get_settings
from app.state_machine import IllegalTransition

settings = get_settings()
# Prefer repo-root data path
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_DB = os.path.join(_ROOT, "data", "rabt.db")
ledger = Ledger(db_path=os.environ.get("RABT_DB", _DB))
coordinator = Coordinator(ledger)
DEMO_IDS: dict[str, str] = {}
_tick_task: asyncio.Task | None = None


async def _background_tick() -> None:
    while True:
        try:
            db = await ledger.connect()
            try:
                await coordinator.tick(db)
            finally:
                await db.close()
        except Exception:
            pass
        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global DEMO_IDS, _tick_task
    demo_clock.reset()
    # Delete the configured ledger path (not a hardcoded default) on startup
    db_path = ledger.db_path
    if os.path.exists(db_path) and os.environ.get("RABT_KEEP_DB") != "1":
        try:
            os.remove(db_path)
        except OSError:
            pass
    DEMO_IDS = await seed_demo(ledger, coordinator)
    _tick_task = asyncio.create_task(_background_tick())
    yield
    if _tick_task:
        _tick_task.cancel()
        try:
            await _tick_task
        except asyncio.CancelledError:
            pass


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


@app.middleware("http")
async def demo_write_auth(request: Request, call_next):
    """Read-only guest access; writes need persona or ingest secret."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return await call_next(request)
    path = request.url.path
    if path in {"/healthz", "/"}:
        return await call_next(request)
    if path.startswith("/webhook/") or path == "/cases/ingest":
        secret = request.headers.get("X-Rabt-Ingest-Secret")
        if not ingest_secret_ok(secret):
            return JSONResponse({"detail": "invalid or missing X-Rabt-Ingest-Secret"}, status_code=401)
        return await call_next(request)
    persona = request.headers.get("X-Rabt-Persona")
    if not persona:
        return JSONResponse({"detail": "X-Rabt-Persona header required for write routes"}, status_code=401)
    if not persona_allowed(persona):
        return JSONResponse({"detail": f"unknown demo persona: {persona}"}, status_code=403)
    request.state.persona = persona
    return await call_next(request)


@app.exception_handler(KeyError)
async def key_error_handler(_request: Request, exc: KeyError):
    detail = str(exc.args[0]) if exc.args else "not found"
    if detail and not detail.startswith("case"):
        detail = f"case not found: {detail}" if detail else "case not found"
    return JSONResponse({"detail": detail or "case not found"}, status_code=404)


class ObservationIn(BaseModel):
    patient_id: str
    observation: dict[str, Any]
    patient: dict[str, Any] = Field(default_factory=dict)
    plan_id: str | None = None
    consent_messaging: bool = True
    idempotency_key: str | None = None
    siblings: list[dict[str, Any]] = Field(default_factory=list)


class TeachbackIn(BaseModel):
    answers: list[str] = Field(min_length=1)


class BookIn(BaseModel):
    option_id: str


class DecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str = Field(default="", max_length=500)
    # user_id ignored if sent — identity comes from X-Rabt-Persona
    user_id: str | None = None


class CloseIn(BaseModel):
    human_reason_code: str | None = None
    human_signer: str | None = None
    # four_eyes_ok removed — dual approval via /approvals only; extra body fields ignored


class OutcomeIn(BaseModel):
    outcome_ref: str = Field(max_length=200)
    outcome_note: str = Field(default="", max_length=500)


class QuestionIn(BaseModel):
    question: str = Field(max_length=500)


class DeclineIn(BaseModel):
    reason: str = Field(max_length=500)
    actor: str = "human:owner"


@app.get("/")
async def root():
    return {
        "name": "Rabt Care-Loop Orchestrator",
        "version": app.version,
        "docs": "/docs",
        "healthz": "/healthz",
    }


@app.get("/healthz")
async def healthz():
    return {
        "ok": True,
        "service": "rabt-orchestrator",
        "guest_mode": settings.guest_mode,
        "content_safety": bool(settings.content_safety_endpoint),
        "llm": settings.llm_enabled,
        "mcp_in_demo_path": False,
    }


@app.post("/demo/advance")
async def demo_advance(minutes: float = Query(15, gt=0, le=1440)):
    """Fast-forward the demo clock and run one HITL/ladder tick."""
    offset = demo_clock.advance(minutes)
    db = await ledger.connect()
    try:
        tick_result = await coordinator.tick(db)
        return {
            "ok": True,
            "advanced_minutes": minutes,
            "offset_seconds": offset,
            "now": demo_clock.now(),
            "tick": tick_result,
        }
    finally:
        await db.close()


@app.post("/demo/reset")
async def demo_reset():
    """Wipe and reseed the shared demo (persona-protected)."""
    global DEMO_IDS
    demo_clock.reset()
    db_path = ledger.db_path
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except OSError:
        # Fall back to truncating tables if the file is locked
        db = await ledger.connect()
        try:
            for table in (
                "approval_votes",
                "approvals",
                "queue_items",
                "cases",
                "processed_events",
            ):
                await db.execute(f"DELETE FROM {table}")
            await db.commit()
        finally:
            await db.close()
    DEMO_IDS = await seed_demo(ledger, coordinator)
    return {
        "ok": True,
        "cases": DEMO_IDS,
        "demo_clock_offset_seconds": demo_clock.offset_seconds(),
        "note": "Shared demo reseeding. Links use stable case ids (case-gc01-fatima, …).",
    }


@app.get("/demo")
async def demo_index():
    return {
        "banner": "Synthetic data. Demo only. Not a diagnosis. Not for clinical use. Shared demo — data resets on restart or Reset demo.",
        "demo_clock_offset_seconds": demo_clock.offset_seconds(),
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


def _persona(request: Request) -> str:
    return getattr(request.state, "persona", None) or request.headers.get("X-Rabt-Persona") or ""


@app.post("/cases/{case_id}/accept")
async def accept(case_id: str, request: Request, actor: str | None = None):
    db = await ledger.connect()
    try:
        return await coordinator.accept_ownership(db, case_id, _persona(request) or actor or "human:gp")
    except IllegalTransition as e:
        raise HTTPException(400, str(e)) from e
    finally:
        await db.close()


@app.post("/cases/{case_id}/decline")
async def decline(case_id: str, body: DeclineIn, request: Request):
    db = await ledger.connect()
    try:
        actor = _persona(request) or body.actor
        return await coordinator.decline_ownership(db, case_id, actor, body.reason)
    except IllegalTransition as e:
        raise HTTPException(400, str(e)) from e
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
    except IllegalTransition as e:
        raise HTTPException(400, str(e)) from e
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
async def attend(case_id: str, note: str = "Encounter completed"):
    db = await ledger.connect()
    try:
        return await coordinator.mark_attended(db, case_id, note)
    except IllegalTransition as e:
        raise HTTPException(400, str(e)) from e
    finally:
        await db.close()


@app.post("/cases/{case_id}/outcome")
async def record_outcome(case_id: str, body: OutcomeIn):
    db = await ledger.connect()
    try:
        return await coordinator.record_outcome(
            db, case_id, outcome_ref=body.outcome_ref, outcome_note=body.outcome_note
        )
    except IllegalTransition as e:
        raise HTTPException(400, str(e)) from e
    finally:
        await db.close()


@app.post("/cases/{case_id}/close")
async def close_case(case_id: str, request: Request, body: CloseIn | None = None):
    db = await ledger.connect()
    try:
        human = body.model_dump(exclude_none=True) if body else {}
        human.pop("four_eyes_ok", None)
        # Requester identity always comes from the persona header
        persona = _persona(request)
        if persona:
            human["human_signer"] = persona
            human["requested_by"] = persona
        return await coordinator.try_close(db, case_id, human=human or None)
    except IllegalTransition as e:
        msg = str(e)
        code = 409 if "already Closed" in msg else 400
        raise HTTPException(code, msg) from e
    except KeyError:
        raise HTTPException(404, "case not found") from None
    finally:
        await db.close()


@app.post("/cases/{case_id}/reject-referral")
async def reject_referral(case_id: str, reason: str = "capacity"):
    db = await ledger.connect()
    try:
        return await coordinator.reject_referral(db, case_id, reason)
    except IllegalTransition as e:
        raise HTTPException(400, str(e)) from e
    finally:
        await db.close()


@app.post("/cases/{case_id}/consent/withdraw")
async def withdraw(case_id: str):
    db = await ledger.connect()
    try:
        return await coordinator.withdraw_consent(db, case_id)
    except IllegalTransition as e:
        raise HTTPException(400, str(e)) from e
    finally:
        await db.close()


@app.post("/cases/{case_id}/reassure")
async def reassure(case_id: str, body: QuestionIn):
    db = await ledger.connect()
    try:
        return await coordinator.reassure(db, case_id, body.question)
    except IllegalTransition as e:
        raise HTTPException(400, str(e)) from e
    finally:
        await db.close()


@app.post("/cases/{case_id}/econsult")
async def econsult(case_id: str):
    db = await ledger.connect()
    try:
        return await coordinator.econsult_packet(db, case_id)
    except IllegalTransition as e:
        raise HTTPException(400, str(e)) from e
    finally:
        await db.close()


@app.post("/cases/{case_id}/escalation/handle")
async def handle_escalation(case_id: str, request: Request, actor: str | None = None):
    db = await ledger.connect()
    try:
        return await coordinator.human_handle_escalation(
            db, case_id, _persona(request) or actor or "human:coordinator"
        )
    except IllegalTransition as e:
        raise HTTPException(400, str(e)) from e
    finally:
        await db.close()


@app.get("/queue")
async def queue():
    db = await ledger.connect()
    try:
        return await list_queue(db)
    finally:
        await db.close()


@app.get("/approvals")
async def approvals(status: str = "pending", action: str | None = None):
    db = await ledger.connect()
    try:
        return await list_approvals(db, status=status, action=action)
    finally:
        await db.close()


@app.post("/approvals/{token}/decision")
async def approval_decision(token: str, body: DecisionIn, request: Request):
    persona = _persona(request)
    if not persona:
        raise HTTPException(401, "X-Rabt-Persona required")
    if body.decision not in {"approved", "rejected"}:
        raise HTTPException(422, "decision must be approved or rejected")
    db = await ledger.connect()
    try:
        result = await submit_decision(db, token, persona, body.decision, body.reason)
        if result.get("status") == "threshold_met" and result.get("action") == "exceptional_closure":
            cur = await db.execute(
                "SELECT user_id FROM approval_votes WHERE token = ? AND decision = 'approved' ORDER BY at ASC",
                (token,),
            )
            approvers = [r["user_id"] for r in await cur.fetchall()]
            try:
                case = await coordinator.complete_approved_closure(
                    db,
                    result["case_id"],
                    approvers=approvers,
                    evidence=result.get("evidence") or {},
                )
            except IllegalTransition as e:
                # Leave approval pending so votes can be retried after a fix (#25)
                raise HTTPException(400, str(e)) from e
            await mark_approved(db, token)
            result["status"] = "approved"
            result["case"] = case
        elif result.get("status") == "rejected" and result.get("action") == "exceptional_closure":
            case = await coordinator.cancel_exceptional_closure(
                db,
                result["case_id"],
                reason=f"rejected by {persona}",
                actor=persona,
            )
            result["case"] = case
        return result
    except ApprovalError as e:
        raise HTTPException(getattr(e, "status_code", 403), str(e)) from e
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
    from app.kpis import compute_kpis

    db = await ledger.connect()
    try:
        cases = await ledger.list_cases(db)
        return compute_kpis(cases)
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
