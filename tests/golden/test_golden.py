"""Golden cases against the in-process orchestrator (synthetic)."""

from __future__ import annotations

import os
import tempfile

import pytest

from app.coordinator import Coordinator
from app.demo_seed import (
    obs_bp_critical,
    obs_fit_positive,
    obs_glucose_bad_unit,
    obs_hba1c,
)
from app.ledger import Ledger
from app.reference_data import DEMO_PATIENTS, PROVIDERS
from agents.navigator.scoring import score_options
from agents.closure.verifier import verify_closure
from agents.common.guardrails import no_diagnosis
from agents.reassurance.agent import run as reassure_run


@pytest.fixture
async def orch():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    ledger = Ledger(db_path=path)
    coord = Coordinator(ledger)
    db = await ledger.connect()
    yield ledger, coord, db
    await db.close()
    try:
        os.remove(path)
    except OSError:
        pass


@pytest.mark.asyncio
async def test_gc01_hba1c_flow(orch):
    ledger, coord, db = orch
    fatima = DEMO_PATIENTS["fatima"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "gc01",
            "patient_id": fatima["id"],
            "patient": fatima,
            "observation": obs_hba1c(fatima["id"], 7.2, "o1"),
        },
    )
    assert case["state"] == "AwaitingOwner"
    assert case["urgency"] == "URGENT"
    case = await coord.accept_ownership(db, case["case_id"], "human:gp")
    case = await coord.notify_patient(db, case["case_id"])
    assert case["state"] == "PatientNotified"
    assert "ليس تشخيصاً" in case["messages"][-1]["text"] or "not a diagnosis" in case["messages"][-1]["text"].lower()
    answers = [q["correct"] for q in case["messages"][-1]["teachback"]]
    case = await coord.submit_teachback(db, case["case_id"], answers)
    assert case["state"] in {"Referred", "Understood"}
    opts = case.get("options") or []
    assert opts
    assert all(o.get("in_network") for o in opts)
    case = await coord.book(db, case["case_id"], opts[0]["id"])
    case = await coord.mark_attended(db, case["case_id"], "Plan agreed")
    assert case["state"] == "Closed"


@pytest.mark.asyncio
async def test_gc02_critical_no_llm_values(orch):
    ledger, coord, db = orch
    omar = DEMO_PATIENTS["omar"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "gc02",
            "patient_id": omar["id"],
            "patient": omar,
            "observation": obs_bp_critical(omar["id"], 190, "o2"),
        },
    )
    assert case["state"] == "Escalated"
    assert case["urgency"] == "CRITICAL"
    msg = case["messages"][-1]
    assert msg.get("includes_values") is False
    assert "190" not in (msg.get("text") or "")


@pytest.mark.asyncio
async def test_gc05_out_of_network_excluded(orch):
    opts = score_options("specialist_gastro", {"net-plan-b"}, PROVIDERS, "en")
    assert opts
    assert all(o["in_network"] for o in opts)
    assert all(o["id"] != "org-gastro-oon" for o in opts)


@pytest.mark.asyncio
async def test_gc07_data_query(orch):
    ledger, coord, db = orch
    omar = DEMO_PATIENTS["omar"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "gc07",
            "patient_id": omar["id"],
            "patient": omar,
            "observation": obs_glucose_bad_unit(omar["id"], "o7"),
        },
    )
    assert case["state"] == "DataQuery"


@pytest.mark.asyncio
async def test_gc09_reassurance_no_diagnosis():
    res = await reassure_run(
        {"case_id": "x", "inputs": {"question": "Do I have cancer after positive FIT?", "language": "en"}}
    )
    assert no_diagnosis(res["outputs"]["answer"])
    assert res["outputs"].get("citations")


@pytest.mark.asyncio
async def test_gc10_false_closure_blocked(orch):
    ledger, coord, db = orch
    omar = DEMO_PATIENTS["omar"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "gc10",
            "patient_id": omar["id"],
            "patient": omar,
            "observation": obs_hba1c(omar["id"], 6.9, "o10"),
        },
    )
    await coord.accept_ownership(db, case["case_id"], "human:gp")
    # Attempt premature close from Owned via try_close without evidence
    case = await ledger.get_case(db, case["case_id"])
    result = verify_closure(case.get("evidence") or {})
    assert result["closable"] is False
    # Force closure pending path
    await coord.notify_patient(db, case["case_id"])
    case = await ledger.get_case(db, case["case_id"])
    tb = [q["correct"] for q in case["messages"][-1]["teachback"]]
    case = await coord.submit_teachback(db, case["case_id"], tb)
    case = await coord.book(db, case["case_id"], case["options"][0]["id"])
    # try close without attend
    from app.state_machine import S
    from app.state_machine import transition, IllegalTransition

    try:
        transition(S.BOOKED, S.CLOSED, actor="agent:closure", reason="bad", evidence={"closure_ok": True})
        assert False, "BOOKED -> CLOSED must be illegal"
    except IllegalTransition:
        pass
    blocked = await coord.try_close(db, case["case_id"])
    # still not closed
    assert blocked["state"] != "Closed"
