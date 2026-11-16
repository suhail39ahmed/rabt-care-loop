"""Two-person closure + outcome evidence (#2, #3)."""

from __future__ import annotations

import os
import tempfile

import pytest
from app.coordinator import Coordinator
from app.demo_seed import obs_hba1c
from app.hitl import ApprovalError, list_approvals, submit_decision
from app.ledger import Ledger
from app.reference_data import DEMO_PATIENTS


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


async def _owned_case(coord, db):
    fatima = DEMO_PATIENTS["fatima"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "closure-hitl",
            "patient_id": fatima["id"],
            "patient": fatima,
            "observation": obs_hba1c(fatima["id"], 7.0, "obs-close"),
        },
    )
    case = await coord.accept_ownership(db, case["case_id"], "human:gp-aisha")
    return case


@pytest.mark.asyncio
async def test_four_eyes_ok_in_body_has_no_effect(orch):
    ledger, coord, db = orch
    case = await _owned_case(coord, db)
    result = await coord.try_close(
        db,
        case["case_id"],
        human={
            "human_reason_code": "exceptional",
            "human_signer": "human:gp-aisha",
            "four_eyes_ok": True,
        },
    )
    assert result["state"] == "ClosurePending"
    assert result["state"] != "ClosedByHuman"
    approvals = await list_approvals(db)
    assert len(approvals) == 1
    assert approvals[0]["required"] == 2


@pytest.mark.asyncio
async def test_attendance_without_outcome_blocks_or_routes_to_approval(orch):
    ledger, coord, db = orch
    case = await _owned_case(coord, db)
    case = await coord.notify_patient(db, case["case_id"])
    tb = [q["correct"] for q in case["messages"][-1]["teachback"]]
    case = await coord.submit_teachback(db, case["case_id"], tb)
    case = await coord.book(db, case["case_id"], case["options"][0]["id"])
    case = await coord.mark_attended(db, case["case_id"], "seen")
    assert case["state"] != "Closed"
    evidence = case.get("evidence") or {}
    assert evidence.get("attended_encounter") is True
    assert not evidence.get("outcome_document")
    # bounced to Attended after missing outcome (#53)
    assert case["state"] == "Attended"


@pytest.mark.asyncio
async def test_attendance_plus_outcome_closes(orch):
    ledger, coord, db = orch
    case = await _owned_case(coord, db)
    case = await coord.notify_patient(db, case["case_id"])
    tb = [q["correct"] for q in case["messages"][-1]["teachback"]]
    case = await coord.submit_teachback(db, case["case_id"], tb)
    case = await coord.book(db, case["case_id"], case["options"][0]["id"])
    case = await coord.mark_attended(db, case["case_id"], "seen")
    case = await coord.record_outcome(
        db, case["case_id"], outcome_ref="Encounter/enc-1", outcome_note="Plan agreed"
    )
    assert case["state"] == "Closed"
    evidence = case.get("evidence") or {}
    assert evidence.get("outcome_ref") == "Encounter/enc-1"
    assert evidence.get("outcome_document") is True


@pytest.mark.asyncio
async def test_two_person_closure_gc08_flow(orch):
    """Exceptional close: one vote keeps open; two distinct non-requester votes close."""
    ledger, coord, db = orch
    case = await _owned_case(coord, db)
    case = await coord.try_close(
        db,
        case["case_id"],
        human={"human_reason_code": "declined_care", "human_signer": "human:gp-aisha"},
    )
    assert case["state"] == "ClosurePending"
    approvals = await list_approvals(db)
    assert len(approvals) == 1
    token = approvals[0]["token"]

    with pytest.raises(ApprovalError, match="requester"):
        await submit_decision(db, token, "human:gp-aisha", "approved")

    pending = await submit_decision(db, token, "human:dr-sara", "approved")
    assert pending["status"] == "pending"
    case = await ledger.get_case(db, case["case_id"])
    assert case["state"] == "ClosurePending"

    # same user again — still one vote
    again = await submit_decision(db, token, "human:dr-sara", "approved")
    assert again["status"] == "pending"
    assert again["votes"] == 1

    threshold = await submit_decision(db, token, "human:supervisor", "approved")
    assert threshold["status"] == "threshold_met"
    # Approval must still be pending until transition succeeds
    still = await list_approvals(db)
    assert any(a["token"] == token for a in still)

    case = await coord.complete_approved_closure(
        db,
        case["case_id"],
        approvers=["human:dr-sara", "human:supervisor"],
        evidence=threshold.get("evidence") or {},
    )
    assert case["state"] == "ClosedByHuman"
    evidence = case.get("evidence") or {}
    assert set(evidence.get("approvers") or []) == {"human:dr-sara", "human:supervisor"}
