"""Runtime tool scopes + MAX_STEPS per chain (#34)."""

from __future__ import annotations

import os
import tempfile

import pytest
from app.coordinator import MAX_STEPS, Coordinator
from app.demo_seed import obs_hba1c
from app.ledger import Ledger
from app.reference_data import DEMO_PATIENTS
from app.tools import ToolScopeError, assert_tool_allowed


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
async def test_out_of_scope_tool_refused_and_logged(orch):
    ledger, coord, db = orch
    fatima = DEMO_PATIENTS["fatima"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "scope-refuse",
            "patient_id": fatima["id"],
            "patient": fatima,
            "observation": obs_hba1c(fatima["id"], 7.0, "obs-scope"),
        },
    )
    case_id = case["case_id"]
    with pytest.raises(ToolScopeError):
        await coord._call_tool(db, case_id, "triage", "send_message", lambda: "nope")
    case = await ledger.get_case(db, case_id)
    labels = [t.get("label") for t in case.get("timeline") or []]
    assert any("Tool refused" in (l or "") for l in labels)


@pytest.mark.asyncio
async def test_happy_path_never_hits_max_steps(orch):
    ledger, coord, db = orch
    fatima = DEMO_PATIENTS["fatima"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "happy-max",
            "patient_id": fatima["id"],
            "patient": fatima,
            "observation": obs_hba1c(fatima["id"], 7.1, "obs-happy"),
        },
    )
    case_id = case["case_id"]
    assert coord._step_counts.get(case_id, 0) <= MAX_STEPS
    case = await coord.accept_ownership(db, case_id, "human:gp-aisha")
    case = await coord.notify_patient(db, case_id)
    tb = [q["correct"] for q in case["messages"][-1]["teachback"]]
    case = await coord.submit_teachback(db, case_id, tb)
    case = await coord.book(db, case_id, case["options"][0]["id"])
    case = await coord.mark_attended(db, case_id, "seen")
    case = await coord.record_outcome(
        db, case_id, outcome_ref="Encounter/demo", outcome_note="ok"
    )
    assert case["state"] in {"Closed", "ClosurePending", "Owned", "ClosedByHuman"}
    # Each public method resets the chain — never stuck above MAX_STEPS
    assert coord._step_counts.get(case_id, 0) <= MAX_STEPS


@pytest.mark.asyncio
async def test_looping_chain_stops_at_max_steps(orch):
    ledger, coord, db = orch
    fatima = DEMO_PATIENTS["fatima"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "loop-max",
            "patient_id": fatima["id"],
            "patient": fatima,
            "observation": obs_hba1c(fatima["id"], 6.9, "obs-loop"),
        },
    )
    case_id = case["case_id"]
    coord._begin_chain(case_id)
    # Force repeated delegation without reset
    for _ in range(MAX_STEPS + 1):
        raw = await coord._delegate(
            db,
            case_id,
            "triage",
            triage_noop(),
        )
        if raw is None:
            break
    else:
        pytest.fail("expected MAX_STEPS to stop the chain")
    case = await ledger.get_case(db, case_id)
    labels = [t.get("label") for t in case.get("timeline") or []]
    assert "MAX_STEPS exceeded" in labels


async def triage_noop():
    return {
        "case_id": "x",
        "step": "triage",
        "status": "ok",
        "outputs": {},
        "evidence_refs": [],
    }


def test_assert_tool_allowed_still_unit_tested():
    assert_tool_allowed("closure", "read_case_bundle")
    with pytest.raises(ToolScopeError):
        assert_tool_allowed("closure", "send_message")
