"""Expert call outcome + concern classification (#86 #87 #95)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from agents.intent.classify import classify_concern
from fastapi.testclient import TestClient


def test_crisis_is_deterministic():
    out = classify_concern("I want to kill myself")
    assert out["crisis"] is True
    assert out["intent"] == "crisis"


def test_cost_concern():
    out = classify_concern("This is too expensive for me")
    assert out["intent"] == "cost"
    assert out["crisis"] is False


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
        yield c
    Path(path).unlink(missing_ok=True)


STAFF = {"X-Rabt-Persona": "human:coordinator-sara"}


def test_critical_handle_requires_call_outcome(client):
    demo = client.get("/demo").json()
    cid = demo["cases"]["gc02_critical_bp"]
    case = client.get(f"/cases/{cid}").json()
    assert case["urgency"] == "CRITICAL"
    # Force Escalated if needed — seed may already escalate
    r = client.post(f"/cases/{cid}/escalation/handle", headers=STAFF)
    assert r.status_code == 400
    assert "call outcome" in r.text.lower() or "outcome" in r.text.lower()
    r = client.post(
        f"/cases/{cid}/call/outcome",
        headers=STAFF,
        json={"outcome": "reached_going_now"},
    )
    assert r.status_code == 200
    r = client.post(f"/cases/{cid}/escalation/handle", headers=STAFF)
    assert r.status_code == 200
    assert r.json()["state"] == "Owned"
