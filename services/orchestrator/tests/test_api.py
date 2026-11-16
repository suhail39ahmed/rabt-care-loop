"""HTTP-level API tests for auth, approvals, and error shapes (#29–#31, #39)."""

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
    monkeypatch.delenv("RABT_INGEST_SECRET", raising=False)

    import app.main as main_mod
    from app.coordinator import Coordinator
    from app.ledger import Ledger

    ledger = Ledger(db_path=path)
    main_mod.ledger = ledger
    main_mod.coordinator = Coordinator(ledger)
    main_mod.DEMO_IDS = {}

    with TestClient(main_mod.app) as c:
        yield c

    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


PERSONA = {"X-Rabt-Persona": "human:coordinator-sara"}
PERSONA_B = {"X-Rabt-Persona": "human:gp-aisha"}


def test_write_without_persona_401(client):
    r = client.post("/demo/advance?minutes=1")
    assert r.status_code == 401


def test_unknown_persona_403(client):
    r = client.post("/demo/advance?minutes=1", headers={"X-Rabt-Persona": "anyone"})
    assert r.status_code == 403


def test_healthz_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "content_safety" in body
    assert "mcp_in_demo_path" in body


def test_decision_maybe_422(client):
    r = client.post(
        "/approvals/not-a-token/decision",
        headers=PERSONA,
        json={"decision": "maybe"},
    )
    assert r.status_code == 422


def test_unknown_case_routes_404(client):
    for path in (
        "/cases/case-nope/close",
        "/cases/case-nope/attend",
        "/cases/case-nope/notify",
        "/cases/case-nope/escalation/handle",
    ):
        r = client.post(path, headers=PERSONA, json={})
        assert r.status_code == 404, f"{path} -> {r.status_code} {r.text}"


def test_get_unknown_case_404(client):
    r = client.get("/cases/case-nope")
    assert r.status_code == 404


def test_advance_minutes_bounds(client):
    assert client.post("/demo/advance?minutes=-1", headers=PERSONA).status_code == 422
    assert client.post("/demo/advance?minutes=0", headers=PERSONA).status_code == 422
    assert client.post("/demo/advance?minutes=100000", headers=PERSONA).status_code == 422
    assert client.post("/demo/advance?minutes=15", headers=PERSONA).status_code == 200


def test_oversize_question_422(client):
    demo = client.get("/demo").json()
    case_id = demo["cases"].get("gc01_fatima_hba1c") or next(iter(demo["cases"].values()))
    r = client.post(
        f"/cases/{case_id}/reassure",
        headers=PERSONA,
        json={"question": "x" * 501},
    )
    assert r.status_code == 422


def test_unknown_approval_token_404(client):
    r = client.post(
        "/approvals/zzz-missing/decision",
        headers=PERSONA,
        json={"decision": "approved"},
    )
    assert r.status_code == 404


def test_approvals_action_filter_hides_critical(client):
    all_appr = client.get("/approvals").json()
    closure_only = client.get("/approvals?action=exceptional_closure").json()
    assert all(a["action"] == "exceptional_closure" for a in closure_only)
    critical = [a for a in all_appr if a["action"] == "critical"]
    if critical:
        assert not any(a["action"] == "critical" for a in closure_only)


def test_demo_seeded(client):
    demo = client.get("/demo").json()
    assert demo.get("cases")
    assert len(demo["cases"]) >= 1


def test_close_requester_from_persona_not_body(client):
    demo = client.get("/demo").json()
    case_id = demo["cases"].get("gc01_fatima_hba1c") or next(iter(demo["cases"].values()))
    client.post(f"/cases/{case_id}/accept", headers=PERSONA_B)
    r = client.post(
        f"/cases/{case_id}/close",
        headers=PERSONA,
        json={"human_reason_code": "exceptional_closure", "human_signer": "human:gp-aisha"},
    )
    assert r.status_code == 200
    approvals = client.get("/approvals?action=exceptional_closure").json()
    if approvals:
        assert approvals[-1]["requested_by"] == "human:coordinator-sara"
        vote = client.post(
            f"/approvals/{approvals[-1]['token']}/decision",
            headers=PERSONA,
            json={"decision": "approved"},
        )
        assert vote.status_code == 403
