"""#54 teach-back redaction + #55 webhook/KeyError handling."""

from __future__ import annotations

import json
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

    with TestClient(main_mod.app, raise_server_exceptions=True) as c:
        yield c, main_mod

    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


PERSONA = {"X-Rabt-Persona": "human:coordinator-sara"}


def _has_correct(obj) -> bool:
    if isinstance(obj, dict):
        if "correct" in obj:
            return True
        return any(_has_correct(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_correct(v) for v in obj)
    return False


def test_get_case_strips_teachback_correct(client):
    c, _ = client
    c.post("/demo/reset", headers=PERSONA)
    body = c.get("/cases/case-gc01-fatima").json()
    assert body["case_id"] == "case-gc01-fatima"
    assert not _has_correct(body)


def test_webhook_invalid_json_400(client):
    c, _ = client
    r = c.post(
        "/webhook/fhir",
        content=b"not json",
        headers={"Content-Type": "application/json", **PERSONA},
    )
    # ingest path uses secret middleware bypass when no secret configured
    assert r.status_code == 400
    assert r.json()["detail"] == "invalid JSON"


def test_unknown_case_routes_uniform_404(client):
    c, _ = client
    for path in (
        "/cases/case-nope/close",
        "/cases/case-nope/attend",
        "/cases/case-nope/notify",
        "/cases/case-nope/escalation/handle",
        "/cases/case-nope/outcome",
    ):
        kwargs = {"headers": PERSONA}
        if path.endswith("/close"):
            kwargs["json"] = {"human_reason_code": "dup"}
        elif path.endswith("/outcome"):
            kwargs["json"] = {"outcome_ref": "Encounter/x"}
        r = c.post(path, **kwargs)
        assert r.status_code == 404, f"{path} -> {r.status_code} {r.text}"
        assert r.json() == {"detail": "case not found"}


def test_keyerror_not_mapped_to_404(client):
    c, main_mod = client
    assert KeyError not in main_mod.app.exception_handlers

    @main_mod.app.get("/__test_keyerror")
    async def _boom():
        raise KeyError("internal-bug")

    with pytest.raises(KeyError):
        c.get("/__test_keyerror")
