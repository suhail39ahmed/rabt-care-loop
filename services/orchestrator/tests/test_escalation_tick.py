"""Escalation ladder tick + demo clock (#6)."""

from __future__ import annotations

import os
import tempfile

import pytest
from app import demo_clock
from app.coordinator import Coordinator
from app.demo_seed import obs_hba1c
from app.hitl import list_approvals, request_approval
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


@pytest.mark.asyncio
async def test_exceptional_closure_timeout_never_closes(orch):
    ledger, coord, db = orch
    fatima = DEMO_PATIENTS["fatima"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "timeout-close",
            "patient_id": fatima["id"],
            "patient": fatima,
            "observation": obs_hba1c(fatima["id"], 7.1, "o-to"),
        },
    )
    case = await coord.accept_ownership(db, case["case_id"], "human:gp")
    await request_approval(
        db,
        case["case_id"],
        "exceptional_closure",
        approvers_required=2,
        sla_seconds=60,
        requested_by="human:gp",
    )
    demo_clock.advance(2)
    result = await coord.tick(db)
    case = await ledger.get_case(db, case["case_id"])
    assert case["state"] != "Closed"
    assert case["state"] != "ClosedByHuman"
    assert case["case_id"] in result["kept_open"]
    pending = await list_approvals(db)
    assert all(a["case_id"] != case["case_id"] for a in pending)
