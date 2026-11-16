"""Timeline kind is ai only when an LLM actually ran (#70)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from app.state_machine import S


@pytest.fixture()
async def coord_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("RABT_DB", path)
    from app.coordinator import Coordinator
    from app.ledger import Ledger

    ledger = Ledger(db_path=path)
    coord = Coordinator(ledger)
    db = await ledger.connect()
    try:
        yield coord, db, ledger
    finally:
        await db.close()
        Path(path).unlink(missing_ok=True)


async def _to_notified(coord, db, ledger):
    from app.demo_seed import seed_demo

    ids = await seed_demo(ledger, coord)
    case_id = ids["gc01_fatima_hba1c"]
    case = await ledger.get_case(db, case_id)
    if case["state"] == S.AWAITING_OWNER.value:
        await coord.accept_ownership(db, case_id, "human:gp-aisha")
        case = await ledger.get_case(db, case_id)
    if case["state"] == S.OWNED.value:
        case = await coord.notify_patient(db, case_id)
    return case_id, case


@pytest.mark.asyncio
async def test_notify_timeline_calculated_without_llm(coord_db):
    coord, db, ledger = coord_db
    case_id, case = await _to_notified(coord, db, ledger)
    timeline = case.get("timeline") or []
    notify_steps = [t for t in timeline if "→ PatientNotified" in t.get("label", "")]
    assert notify_steps, f"expected notify transition in {timeline}"
    assert not any(m.get("ai_generated") for m in (case.get("messages") or []))
    assert notify_steps[-1]["kind"] == "calculated"


@pytest.mark.asyncio
async def test_reassurance_keyword_is_calculated(coord_db):
    coord, db, ledger = coord_db
    case_id, _ = await _to_notified(coord, db, ledger)
    out = await coord.reassure(db, case_id, "What does HbA1c mean?")
    steps = [t for t in (out.get("timeline") or []) if t.get("label") == "Reassurance answer"]
    assert steps
    assert steps[-1]["kind"] == "calculated"
