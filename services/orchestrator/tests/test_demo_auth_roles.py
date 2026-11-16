"""#52 — demo persona roles, duplicate votes, no patient clinical writes."""

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


CLINICIAN = {"X-Rabt-Persona": "human:gp-aisha"}
PATIENT = {"X-Rabt-Persona": "patient:fatima"}
SUPERVISOR = {"X-Rabt-Persona": "human:supervisor"}
SARA = {"X-Rabt-Persona": "human:coordinator-sara"}


@pytest.mark.parametrize(
    "path,json_body",
    [
        ("/approvals/tok/decision", {"decision": "approved"}),
        ("/cases/case-gc01-fatima/attend", None),
        ("/cases/case-gc01-fatima/outcome", {"outcome_ref": "Encounter/x", "outcome_note": "n"}),
        ("/cases/case-gc02-bp/escalation/handle", None),
        ("/cases/case-gc01-fatima/close", {"human_reason_code": "dup"}),
    ],
)
def test_patient_forbidden_on_clinical_writes(client, path, json_body):
    client.post("/demo/reset", headers=SARA)
    kwargs = {"headers": PATIENT}
    if json_body is not None:
        kwargs["json"] = json_body
    r = client.post(path, **kwargs)
    assert r.status_code == 403, f"{path} -> {r.status_code} {r.text}"


def test_patient_may_teachback(client):
    client.post("/demo/reset", headers=SARA)
    # Fatima may not be in Understood yet; auth must not 403 before state check
    r = client.post(
        "/cases/case-gc01-fatima/teachback",
        headers=PATIENT,
        json={"answers": ["a", "b"]},
    )
    assert r.status_code != 403


def _exceptional_token(client) -> str:
    rows = client.get("/approvals?action=exceptional_closure", headers=SARA).json()
    assert rows, "expected pending exceptional_closure approval"
    return rows[0]["token"]


def test_duplicate_vote_409(client):
    client.post("/demo/reset", headers=SARA)
    case = client.get("/cases/case-gc01-fatima").json()
    r = client.post(
        f"/cases/{case['case_id']}/close",
        headers=CLINICIAN,
        json={"human_reason_code": "dup"},
    )
    assert r.status_code == 200, r.text
    token = _exceptional_token(client)
    first = client.post(
        f"/approvals/{token}/decision",
        headers=SARA,
        json={"decision": "approved"},
    )
    assert first.status_code == 200
    dup = client.post(
        f"/approvals/{token}/decision",
        headers=SARA,
        json={"decision": "approved"},
    )
    assert dup.status_code == 409
    assert "duplicate" in dup.json()["detail"].lower()


def test_alias_persona_canonicalizes_for_vote(client):
    """human:gp collapses to human:gp-aisha — cannot vote twice via alias."""
    client.post("/demo/reset", headers=SARA)
    case = client.get("/cases/case-gc01-fatima").json()
    client.post(
        f"/cases/{case['case_id']}/close",
        headers=SUPERVISOR,
        json={"human_reason_code": "dup"},
    )
    token = _exceptional_token(client)
    first = client.post(
        f"/approvals/{token}/decision",
        headers=CLINICIAN,
        json={"decision": "approved"},
    )
    assert first.status_code == 200, first.text
    alias = client.post(
        f"/approvals/{token}/decision",
        headers={"X-Rabt-Persona": "human:gp"},
        json={"decision": "approved"},
    )
    assert alias.status_code == 409
    assert "duplicate" in alias.json()["detail"].lower()


def test_two_person_close_timeline_actors(client):
    client.post("/demo/reset", headers=SARA)
    case = client.get("/cases/case-gc01-fatima").json()
    client.post(
        f"/cases/{case['case_id']}/close",
        headers=CLINICIAN,
        json={"human_reason_code": "dup"},
    )
    token = _exceptional_token(client)
    client.post(f"/approvals/{token}/decision", headers=SARA, json={"decision": "approved"})
    done = client.post(
        f"/approvals/{token}/decision",
        headers=SUPERVISOR,
        json={"decision": "approved"},
    )
    assert done.status_code == 200, done.text
    body = done.json()
    assert body.get("status") == "approved", body
    closed = body.get("case") or client.get(f"/cases/{case['case_id']}").json()
    assert closed["state"] == "ClosedByHuman"
    approvers = (closed.get("evidence") or {}).get("approvers") or []
    assert "human:coordinator-sara" in approvers
    assert "human:supervisor" in approvers
    assert not any(a.startswith("human:patient:") for a in approvers)
    actors = " ".join(t.get("actor", "") for t in closed.get("timeline") or [])
    assert "human:patient:" not in actors
