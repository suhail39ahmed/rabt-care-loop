"""#25 — exceptional close from any open state with two approvals."""

from __future__ import annotations

import os
import tempfile

import pytest

from app.coordinator import Coordinator
from app.demo_seed import obs_hba1c
from app.hitl import list_approvals, mark_approved, submit_decision
from app.ledger import Ledger
from app.reference_data import DEMO_PATIENTS
from app.state_machine import IllegalTransition, S


OPEN_STATES = [
    "AwaitingOwner",
    "Owned",
    "PatientNotified",
    "Understood",
    "Referred",
    "Booked",
    "Escalated",
    "DataQuery",
    "OnHoldConsent",
]


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


async def _force_state(ledger, db, case_id: str, state: str):
    await ledger.update_case(db, case_id, state=state)


@pytest.mark.asyncio
@pytest.mark.parametrize("start_state", OPEN_STATES)
async def test_two_person_close_from_open_state(orch, start_state: str):
    ledger, coord, db = orch
    fatima = DEMO_PATIENTS["fatima"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": f"close-{start_state}",
            "patient_id": fatima["id"],
            "patient": fatima,
            "observation": obs_hba1c(fatima["id"], 7.0, f"o-{start_state}"),
        },
    )
    if start_state == "Escalated":
        # Critical path uses BP; force after create for parametric coverage
        pass
    await _force_state(ledger, db, case["case_id"], start_state)
    case = await coord.try_close(
        db,
        case["case_id"],
        human={"human_reason_code": "exceptional", "human_signer": "human:gp-aisha"},
    )
    assert case["state"] == "ClosurePending"
    token = (await list_approvals(db))[0]["token"]
    await submit_decision(db, token, "human:coordinator-sara", "approved")
    threshold = await submit_decision(db, token, "human:supervisor", "approved")
    assert threshold["status"] == "threshold_met"
    case = await coord.complete_approved_closure(
        db,
        case["case_id"],
        approvers=["human:coordinator-sara", "human:supervisor"],
        evidence=threshold.get("evidence") or {},
    )
    await mark_approved(db, token)
    assert case["state"] == "ClosedByHuman"
    assert "human:coordinator-sara" in (case.get("evidence") or {}).get("approvers", [])


@pytest.mark.asyncio
async def test_failed_transition_keeps_approval_pending(orch):
    ledger, coord, db = orch
    fatima = DEMO_PATIENTS["fatima"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "close-fail",
            "patient_id": fatima["id"],
            "patient": fatima,
            "observation": obs_hba1c(fatima["id"], 7.0, "o-fail"),
        },
    )
    case = await coord.try_close(
        db,
        case["case_id"],
        human={"human_reason_code": "exceptional", "human_signer": "human:gp-aisha"},
    )
    token = (await list_approvals(db))[0]["token"]
    await submit_decision(db, token, "human:a", "approved")
    threshold = await submit_decision(db, token, "human:b", "approved")
    assert threshold["status"] == "threshold_met"
    # Corrupt state to Closed so transition to ClosedByHuman fails
    await _force_state(ledger, db, case["case_id"], S.CLOSED.value)
    with pytest.raises(IllegalTransition):
        await coord.complete_approved_closure(
            db,
            case["case_id"],
            approvers=["human:a", "human:b"],
            evidence=threshold.get("evidence") or {},
        )
    pending = await list_approvals(db)
    assert any(a["token"] == token for a in pending)


@pytest.mark.asyncio
async def test_terminal_close_rejected(orch):
    ledger, coord, db = orch
    fatima = DEMO_PATIENTS["fatima"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "close-term",
            "patient_id": fatima["id"],
            "patient": fatima,
            "observation": obs_hba1c(fatima["id"], 7.0, "o-term"),
        },
    )
    await _force_state(ledger, db, case["case_id"], "Closed")
    with pytest.raises(IllegalTransition, match="already"):
        await coord.try_close(
            db,
            case["case_id"],
            human={"human_reason_code": "x", "human_signer": "human:gp-aisha"},
        )
