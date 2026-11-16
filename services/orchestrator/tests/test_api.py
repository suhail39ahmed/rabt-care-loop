"""HTTP-level API smoke tests (#39). Deeper cases land with #29–#31."""

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


def test_write_without_persona_401(client):
    assert client.post("/demo/advance?minutes=1").status_code == 401


def test_healthz_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_get_unknown_case_404(client):
    r = client.get("/cases/case-nope")
    assert r.status_code == 404


def test_demo_seeded(client):
    demo = client.get("/demo").json()
    assert demo.get("cases")
    assert len(demo["cases"]) >= 1
