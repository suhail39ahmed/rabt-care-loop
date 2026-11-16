"""HITL queue resolve, consent gate, missing routes (#85)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("RABT_DB", path)
    monkeypatch.setenv("RABT_KEEP_DB", "1")

    import app.main as main_mod
    from app.coordinator import Coordinator
    from app.ledger import Ledger

    ledger = Ledger(db_path=path)
    main_mod.ledger = ledger
    main_mod.coordinator = Coordinator(ledger)
    main_mod.DEMO_IDS = {}

    with TestClient(main_mod.app) as c:
        yield c, main_mod

    Path(path).unlink(missing_ok=True)


STAFF = {"X-Rabt-Persona": "human:coordinator-sara"}


def test_accept_on_hold_consent_409(client):
    c, _ = client
    demo = c.get("/demo").json()
    cid = demo["cases"]["gc01_fatima_hba1c"]
    # Seed leaves Fatima in PatientNotified
    r = c.post(f"/cases/{cid}/consent/withdraw", headers={"X-Rabt-Persona": "patient:fatima"})
    assert r.status_code == 200
    assert r.json()["state"] == "OnHoldConsent"
    r = c.post(f"/cases/{cid}/accept", headers=STAFF)
    assert r.status_code == 409


def test_queue_resolve(client):
    c, main_mod = client
    import asyncio
    from app import hitl

    async def enq():
        db = await main_mod.ledger.connect()
        try:
            return await hitl.enqueue(db, "case-x", "callback", "test item")
        finally:
            await db.close()

    qid = asyncio.run(enq())
    r = c.post(f"/queue/{qid}/resolve", headers=STAFF)
    assert r.status_code == 200
    assert r.json()["status"] == "resolved"
    open_ids = {item["id"] for item in c.get("/queue").json()}
    assert qid not in open_ids


def test_resume_consent_route(client):
    c, _ = client
    demo = c.get("/demo").json()
    cid = demo["cases"]["gc01_fatima_hba1c"]
    c.post(f"/cases/{cid}/consent/withdraw", headers={"X-Rabt-Persona": "patient:fatima"})
    r = c.post(f"/cases/{cid}/consent/resume", headers=STAFF)
    assert r.status_code == 200
    assert r.json()["state"] == "Owned"
