"""#51 — rejected / timed-out two-person close restores prior state."""

from __future__ import annotations

import os
import tempfile

import pytest
from app import demo_clock
from app.coordinator import Coordinator
from app.demo_seed import obs_hba1c
from app.hitl import list_approvals, submit_decision
from app.ledger import Ledger
from app.reference_data import DEMO_PATIENTS


@pytest.fixture
async def orch():
    demo_clock.reset()
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    ledger = Ledger(db_path=path)
    coord = Coordinator(ledger)
    db = await ledger.connect()
    yield ledger, coord, db
    await db.close()
    demo_clock.reset()
    try:
        os.remove(path)
    except OSError:
        pass


async def _booked_case(coord, db, key: str = "booked-restore"):
    fatima = DEMO_PATIENTS["fatima"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": key,
            "patient_id": fatima["id"],
            "patient": fatima,
            "observation": obs_hba1c(fatima["id"], 7.1, f"obs-{key}"),
        },
    )
    case = await coord.accept_ownership(db, case["case_id"], "human:gp-aisha")
    case = await coord.notify_patient(db, case["case_id"])
    tb = [q["correct"] for q in case["messages"][-1]["teachback"]]
    case = await coord.submit_teachback(db, case["case_id"], tb)
    case = await coord.book(db, case["case_id"], case["options"][0]["id"])
    assert case["state"] == "Booked"
    return case


def _closure_fields(evidence: dict) -> dict:
    keys = (
        "pending_approval_token",
        "human_reason_code",
        "human_signer",
        "requested_by",
        "two_person_approved",
        "approvers",
        "four_eyes_ok",
        "pre_closure_state",
    )
    return {k: evidence.get(k) for k in keys if evidence.get(k) is not None}


@pytest.mark.asyncio
async def test_reject_restores_booked_then_evidence_closes(orch):
    ledger, coord, db = orch
    case = await _booked_case(coord, db, "reject-restore")
    case = await coord.try_close(
        db,
        case["case_id"],
        human={"human_reason_code": "dup", "human_signer": "human:gp-aisha"},
    )
    assert case["state"] == "ClosurePending"
    assert (case.get("evidence") or {}).get("pre_closure_state") == "Booked"
    token = (await list_approvals(db))[0]["token"]

    rejected = await submit_decision(db, token, "human:supervisor", "rejected")
    assert rejected["status"] == "rejected"
    case = await coord.cancel_exceptional_closure(
        db,
        case["case_id"],
        reason="rejected by human:supervisor",
        actor="human:supervisor",
    )
    assert case["state"] == "Booked"
    assert _closure_fields(case.get("evidence") or {}) == {}

    case = await coord.mark_attended(db, case["case_id"], "seen")
    case = await coord.record_outcome(
        db, case["case_id"], outcome_ref="Encounter/enc-restore", outcome_note="Plan"
    )
    assert case["state"] == "Closed"


@pytest.mark.asyncio
async def test_timeout_restores_via_tick(orch):
    ledger, coord, db = orch
    case = await _booked_case(coord, db, "timeout-restore")
    case = await coord.try_close(
        db,
        case["case_id"],
        human={"human_reason_code": "dup", "human_signer": "human:gp-aisha"},
    )
    assert case["state"] == "ClosurePending"
    demo_clock.advance(20)
    result = await coord.tick(db)
    assert case["case_id"] in result["kept_open"]
    case = await ledger.get_case(db, case["case_id"])
    assert case["state"] == "Booked"
    assert _closure_fields(case.get("evidence") or {}) == {}
    pending = await list_approvals(db)
    assert all(a["case_id"] != case["case_id"] for a in pending)
