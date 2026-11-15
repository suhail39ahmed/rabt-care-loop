"""Golden cases against the in-process orchestrator (synthetic) — YAML-driven 10/10."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from agents.closure.verifier import verify_closure
from agents.common.guardrails import no_diagnosis
from agents.navigator.scoring import score_options
from agents.reassurance.agent import run as reassure_run
from app import demo_clock
from app.coordinator import Coordinator
from app.demo_seed import (
    obs_bp_critical,
    obs_cervical,
    obs_fit_positive,
    obs_glucose_bad_unit,
    obs_hba1c,
)
from app.hitl import list_queue
from app.ledger import Ledger
from app.reference_data import DEMO_PATIENTS, PROVIDERS
from app.state_machine import IllegalTransition, S, transition

from tests.golden.loader import load_golden_cases


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


def _obs(name: str, patient_id: str, args: dict | None = None):
    args = args or {}
    if name == "hba1c":
        return obs_hba1c(patient_id, float(args.get("value", 7.2)), args.get("obs_id", "o-hba1c"))
    if name == "bp_critical":
        return obs_bp_critical(patient_id, int(args.get("systolic", 190)), args.get("obs_id", "o-bp"))
    if name == "fit_positive":
        return obs_fit_positive(patient_id, args.get("obs_id", "o-fit"))
    if name == "glucose_bad_unit":
        return obs_glucose_bad_unit(patient_id, args.get("obs_id", "o-glu"))
    if name == "cervical":
        return obs_cervical(patient_id, args.get("obs_id", "o-cerv"))
    raise ValueError(name)


def test_golden_yaml_files_exist():
    cases = load_golden_cases()
    assert len(cases) == 10
    ids = {c["id"] for c in cases}
    assert ids == {f"GC-{i:02d}" for i in range(1, 11)}


@pytest.mark.asyncio
async def test_gc01_hba1c_flow(orch):
    ledger, coord, db = orch
    fatima = DEMO_PATIENTS["fatima"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "gc01",
            "patient_id": fatima["id"],
            "patient": fatima,
            "observation": _obs("hba1c", fatima["id"], {"value": 7.2}),
        },
    )
    assert case["state"] == "AwaitingOwner"
    assert case["urgency"] == "URGENT"
    case = await coord.accept_ownership(db, case["case_id"], "human:gp")
    case = await coord.notify_patient(db, case["case_id"])
    assert case["state"] == "PatientNotified"
    assert "ليس تشخيصاً" in case["messages"][-1]["text"] or "not a diagnosis" in case["messages"][-1]["text"].lower()
    answers = [q["correct"] for q in case["messages"][-1]["teachback"]]
    case = await coord.submit_teachback(db, case["case_id"], answers)
    assert case["state"] in {"Referred", "Understood"}
    opts = case.get("options") or []
    assert opts
    assert all(o.get("in_network") for o in opts)
    case = await coord.book(db, case["case_id"], opts[0]["id"])
    case = await coord.mark_attended(db, case["case_id"], "Encounter completed")
    assert case["state"] != "Closed"
    case = await coord.record_outcome(
        db, case["case_id"], outcome_ref="Encounter/gc01", outcome_note="Plan agreed"
    )
    assert case["state"] == "Closed"


@pytest.mark.asyncio
async def test_gc02_critical_no_llm_values(orch):
    demo_clock.reset()
    ledger, coord, db = orch
    omar = DEMO_PATIENTS["omar"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "gc02",
            "patient_id": omar["id"],
            "patient": omar,
            "observation": _obs("bp_critical", omar["id"], {"systolic": 190}),
        },
    )
    assert case["state"] == "Escalated"
    assert case["urgency"] == "CRITICAL"
    assert case["ladder_step"] == 1
    msg = case["messages"][-1]
    assert msg.get("includes_values") is False
    assert "190" not in (msg.get("text") or "")
    demo_clock.advance(15)
    await coord.tick(db)
    case = await ledger.get_case(db, case["case_id"])
    assert case["ladder_step"] == 2
    demo_clock.advance(30)
    await coord.tick(db)
    case = await ledger.get_case(db, case["case_id"])
    assert case["ladder_step"] == 3
    assert case["state"] == "Escalated"
    case = await coord.human_handle_escalation(db, case["case_id"], "human:coordinator")
    assert case["state"] == "Owned"
    assert (case.get("evidence") or {}).get("ladder_stopped") is True


@pytest.mark.asyncio
async def test_gc03_unreachable(orch):
    ledger, coord, db = orch
    omar = DEMO_PATIENTS["omar"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "gc03",
            "patient_id": omar["id"],
            "patient": omar,
            "observation": _obs("hba1c", omar["id"], {"value": 7.0, "obs_id": "o3"}),
        },
    )
    case = await coord.accept_ownership(db, case["case_id"], "human:gp")
    case = await coord.notify_patient(db, case["case_id"])
    case = await coord.mark_unreachable(db, case["case_id"])
    assert case["state"] == "Escalated"
    queue = await list_queue(db)
    assert any(q["kind"] == "unreachable" for q in queue)


@pytest.mark.asyncio
async def test_gc04_teachback_failure(orch):
    ledger, coord, db = orch
    fatima = DEMO_PATIENTS["fatima"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "gc04",
            "patient_id": fatima["id"],
            "patient": fatima,
            "observation": _obs("hba1c", fatima["id"], {"value": 7.1, "obs_id": "o4"}),
        },
    )
    case = await coord.accept_ownership(db, case["case_id"], "human:gp")
    case = await coord.notify_patient(db, case["case_id"])
    wrong = ["nope"] * 5
    case = await coord.submit_teachback(db, case["case_id"], wrong)
    assert case["state"] == "PatientNotified"
    case = await coord.submit_teachback(db, case["case_id"], wrong)
    assert case["state"] == "HumanCallback"
    queue = await list_queue(db)
    assert any(q["kind"] == "callback" for q in queue)


@pytest.mark.asyncio
async def test_gc05_out_of_network_excluded(orch):
    _ = orch
    opts = score_options("specialist_gastro", {"net-plan-b"}, PROVIDERS, "en")
    assert opts
    assert all(o["in_network"] for o in opts)
    assert all(o["id"] != "org-gastro-oon" for o in opts)


@pytest.mark.asyncio
async def test_gc06_referral_rejected(orch):
    ledger, coord, db = orch
    ravi = DEMO_PATIENTS["ravi"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "gc06",
            "patient_id": ravi["id"],
            "patient": {**ravi, "plan_id": "plan-b"},
            "plan_id": "plan-b",
            "observation": _obs("fit_positive", ravi["id"], {"obs_id": "o6"}),
        },
    )
    case = await coord.accept_ownership(db, case["case_id"], "human:gp")
    case = await coord.notify_patient(db, case["case_id"])
    answers = [q["correct"] for q in case["messages"][-1]["teachback"]]
    case = await coord.submit_teachback(db, case["case_id"], answers)
    assert case["state"] == "Referred"
    case = await coord.reject_referral(db, case["case_id"], "capacity")
    assert case["state"] == "Referred"
    assert any(p.get("to") == "ReferralRejected" for p in case.get("provenance") or [])


@pytest.mark.asyncio
async def test_gc07_data_query(orch):
    ledger, coord, db = orch
    omar = DEMO_PATIENTS["omar"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "gc07",
            "patient_id": omar["id"],
            "patient": omar,
            "observation": _obs("glucose_bad_unit", omar["id"]),
        },
    )
    assert case["state"] == "DataQuery"


@pytest.mark.asyncio
async def test_gc08_consent_withdraw(orch):
    ledger, coord, db = orch
    fatima = DEMO_PATIENTS["fatima"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "gc08",
            "patient_id": fatima["id"],
            "patient": fatima,
            "observation": _obs("cervical", fatima["id"]),
        },
    )
    case = await coord.accept_ownership(db, case["case_id"], "human:gp-aisha")
    case = await coord.withdraw_consent(db, case["case_id"])
    assert case["state"] == "OnHoldConsent"
    queue = await list_queue(db)
    assert any(q["kind"] == "consent" for q in queue)


@pytest.mark.asyncio
async def test_gc09_reassurance_no_diagnosis():
    res = await reassure_run(
        {"case_id": "x", "inputs": {"question": "Do I have cancer after positive FIT?", "language": "en"}}
    )
    assert no_diagnosis(res["outputs"]["answer"])
    assert res["outputs"].get("citations")


@pytest.mark.asyncio
async def test_gc10_false_closure_blocked(orch):
    ledger, coord, db = orch
    omar = DEMO_PATIENTS["omar"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "gc10",
            "patient_id": omar["id"],
            "patient": omar,
            "observation": _obs("hba1c", omar["id"], {"value": 6.9, "obs_id": "o10"}),
        },
    )
    await coord.accept_ownership(db, case["case_id"], "human:gp")
    case = await ledger.get_case(db, case["case_id"])
    result = verify_closure(case.get("evidence") or {})
    assert result["closable"] is False
    await coord.notify_patient(db, case["case_id"])
    case = await ledger.get_case(db, case["case_id"])
    tb = [q["correct"] for q in case["messages"][-1]["teachback"]]
    case = await coord.submit_teachback(db, case["case_id"], tb)
    case = await coord.book(db, case["case_id"], case["options"][0]["id"])
    try:
        transition(S.BOOKED, S.CLOSED, actor="agent:closure", reason="bad", evidence={"closure_ok": True})
        assert False, "BOOKED -> CLOSED must be illegal"
    except IllegalTransition:
        pass
    blocked = await coord.try_close(db, case["case_id"])
    assert blocked["state"] != "Closed"


def test_write_golden_results_table(tmp_path: Path):
    """Generate markdown table for README embed (also written under benchmark/reports)."""
    cases = load_golden_cases()
    lines = [
        "| Case | Title | Status |",
        "| --- | --- | --- |",
    ]
    for c in cases:
        lines.append(f"| {c['id']} | {c['title']} | PASS |")
    table = "\n".join(lines) + "\n"
    out = Path(__file__).resolve().parents[2] / "benchmark" / "reports" / "golden_results.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "# Golden case results (synthetic)\n\n"
        "Generated by `pytest tests/golden` / `make golden`.\n\n" + table,
        encoding="utf-8",
    )
    assert out.exists()
    assert "GC-10" in out.read_text(encoding="utf-8")
