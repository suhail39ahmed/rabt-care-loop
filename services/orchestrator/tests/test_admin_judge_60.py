"""Admin KPIs, fairness suppression, evidence pack (#57–#62)."""

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
        yield c
    Path(path).unlink(missing_ok=True)


def test_kpis_have_funnel_fields(client):
    body = client.get("/kpis").json()
    assert "verified_closure_rate" in body
    assert "leak_funnel" in body


def test_fairness_suppresses_small_cells(client):
    body = client.get("/benchmark/fairness").json()
    small = [s for s in body["slices"] if s["n"] < body["small_cell_threshold"]]
    assert small
    assert all(s["suppressed"] and s["n_display"].startswith("<") for s in small)


def test_evidence_pack_bundle(client):
    demo = client.get("/demo").json()
    cid = demo["cases"]["gc01_fatima_hba1c"]
    pack = client.get(f"/cases/{cid}/evidence-pack").json()
    assert pack["resourceType"] == "Bundle"
    assert pack["type"] == "collection"
    types = {e["resource"]["resourceType"] for e in pack["entry"]}
    assert "Observation" in types
    assert "Task" in types
    assert "Provenance" in types


def test_sms_messages_exclude_result_value(client):
    demo = client.get("/demo").json()
    cid = demo["cases"]["gc02_critical_bp"]
    case = client.get(f"/cases/{cid}").json()
    value = str(case.get("result_value") or "")
    for m in case.get("messages") or []:
        blob = f"{m.get('text') or ''} {m.get('text_ar') or ''}"
        if m.get("channel") == "sms" and value:
            assert value not in blob
