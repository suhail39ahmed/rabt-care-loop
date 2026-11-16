"""#50 — close must not freeze the critical escalation ladder."""

from __future__ import annotations

import os
import tempfile

import pytest
from app import demo_clock
from app.coordinator import Coordinator
from app.demo_seed import obs_bp_critical
from app.ledger import Ledger
from app.reference_data import DEMO_PATIENTS
from app.state_machine import IllegalTransition


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
async def test_close_on_critical_escalated_refused_and_ladder_advances(orch):
    ledger, coord, db = orch
    omar = DEMO_PATIENTS["omar"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "gc02-close-guard",
            "patient_id": omar["id"],
            "patient": omar,
            "observation": obs_bp_critical(omar["id"], 190, "obs-close-guard"),
        },
    )
    assert case["urgency"] == "CRITICAL"
    assert case["state"] == "Escalated"
    step0 = int(case.get("ladder_step") or 1)

    with pytest.raises(IllegalTransition, match="Handle escalation before requesting close"):
        await coord.try_close(
            db,
            case["case_id"],
            human={"human_reason_code": "dup", "human_signer": "human:gp"},
        )

    case = await ledger.get_case(db, case["case_id"])
    assert case["state"] == "Escalated"
    assert not (case.get("evidence") or {}).get("pending_approval_token")

    demo_clock.advance(30)
    result = await coord.tick(db)
    assert case["case_id"] in result["ladder_advanced"]
    case = await ledger.get_case(db, case["case_id"])
    assert case["state"] == "Escalated"
    assert int(case.get("ladder_step") or 0) > step0
