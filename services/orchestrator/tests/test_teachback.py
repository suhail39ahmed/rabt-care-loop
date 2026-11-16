"""#26 — teach-back must not pass empty/partial answers."""

from __future__ import annotations

import os
import tempfile

import pytest
from app.coordinator import Coordinator
from app.demo_seed import obs_hba1c
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


@pytest.mark.asyncio
async def test_empty_answers_do_not_pass(orch):
    ledger, coord, db = orch
    fatima = DEMO_PATIENTS["fatima"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "tb-empty",
            "patient_id": fatima["id"],
            "patient": fatima,
            "observation": obs_hba1c(fatima["id"], 7.1, "o-tb1"),
        },
    )
    case = await coord.accept_ownership(db, case["case_id"], "human:gp")
    case = await coord.notify_patient(db, case["case_id"])
    case = await coord.submit_teachback(db, case["case_id"], [])
    assert case["state"] == "PatientNotified"
    assert int(case.get("teachback_fails") or 0) == 1


@pytest.mark.asyncio
async def test_partial_answers_count_as_fail(orch):
    ledger, coord, db = orch
    fatima = DEMO_PATIENTS["fatima"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "tb-partial",
            "patient_id": fatima["id"],
            "patient": fatima,
            "observation": obs_hba1c(fatima["id"], 7.1, "o-tb2"),
        },
    )
    case = await coord.accept_ownership(db, case["case_id"], "human:gp")
    case = await coord.notify_patient(db, case["case_id"])
    questions = case["messages"][-1]["teachback"]
    assert len(questions) >= 2
    case = await coord.submit_teachback(db, case["case_id"], [questions[0]["correct"]])
    assert case["state"] == "PatientNotified"
    assert int(case.get("teachback_fails") or 0) == 1
    case = await coord.submit_teachback(db, case["case_id"], [questions[0]["correct"]])
    assert case["state"] == "HumanCallback"
