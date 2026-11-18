"""Stable seeded case IDs + demo reset (#33)."""

from __future__ import annotations

import os
import tempfile

import pytest
from app.coordinator import Coordinator
from app.demo_seed import seed_demo
from app.ledger import Ledger


@pytest.mark.asyncio
async def test_seed_demo_ids_are_stable():
    ids_runs = []
    for _ in range(2):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        ledger = Ledger(db_path=path)
        coord = Coordinator(ledger)
        ids = await seed_demo(ledger, coord)
        ids_runs.append(ids)
        try:
            os.remove(path)
        except OSError:
            pass
    assert ids_runs[0] == ids_runs[1]
    assert ids_runs[0]["gc01_fatima_hba1c"] == "case-gc01-fatima"
    assert ids_runs[0]["gc02_critical_bp"] == "case-gc02-bp"
    assert ids_runs[0]["gc03_owner"] == "case-gc03-owner"
    assert len(ids_runs[0]) == 10


@pytest.mark.asyncio
async def test_gc03_seeded_awaiting_owner():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    ledger = Ledger(db_path=path)
    coord = Coordinator(ledger)
    ids = await seed_demo(ledger, coord)
    db = await ledger.connect()
    try:
        case = await ledger.get_case(db, ids["gc03_owner"])
        assert case
        assert case["state"] == "AwaitingOwner"
        case = await coord.accept_ownership(db, case["case_id"], "human:gp-aisha")
        assert case["state"] in {"Owned", "PatientNotified"}
    finally:
        await db.close()
        try:
            os.remove(path)
        except OSError:
            pass


@pytest.mark.asyncio
async def test_fatima_greeting_uses_first_name():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    ledger = Ledger(db_path=path)
    coord = Coordinator(ledger)
    ids = await seed_demo(ledger, coord)
    db = await ledger.connect()
    try:
        case = await ledger.get_case(db, ids["gc01_fatima_hba1c"])
        assert case
        assert (case.get("evidence") or {}).get("patient_display_name") == "Fatima"
        assert (case.get("evidence") or {}).get("patient_display_name_ar") == "فاطمة"
        msg = case["messages"][-1]
        assert "Fatima" in (msg.get("text") or "") or "فاطمة" in (msg.get("text") or "")
        assert msg.get("by_lang", {}).get("en", {}).get("text")
        assert "Fatima" in (msg["by_lang"]["en"]["text"] or "")
        assert "فاطمة" in (msg["by_lang"]["ar"]["text"] or "")
        assert "Patient" not in (msg["by_lang"]["en"]["text"] or "")
        # EN teach-back present with correct answers
        en_tb = msg["by_lang"]["en"]["teachback"]
        assert en_tb and all(q.get("correct") for q in en_tb)
        assert case["state"] == "PatientNotified"
    finally:
        await db.close()
        try:
            os.remove(path)
        except OSError:
            pass
