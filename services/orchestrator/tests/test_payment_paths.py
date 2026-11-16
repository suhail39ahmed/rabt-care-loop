"""Navigator payment paths: cashless at network hospitals first, pay-and-claim reimbursement tracked as a task."""

from __future__ import annotations

import os
import tempfile

import pytest
from agents.navigator.payment import advance_claim, new_claim, payment_path
from agents.navigator.scoring import score_options
from app import demo_clock
from app.coordinator import Coordinator
from app.demo_seed import obs_fit_positive
from app.insurer import ALLOWED_FIELDS, payment_options, submit_claim
from app.ledger import Ledger
from app.reference_data import DEMO_PATIENTS, PLANS, PROVIDERS

PLAN_B = PLANS["plan-b"]


def _gastro(plan_id: str, **kw):
    plan = PLANS[plan_id]
    return score_options("specialist_gastro", {plan["network_id"]}, PROVIDERS, "en", plan, **kw)


def test_cashless_network_option_ranks_first():
    opts = _gastro("plan-b")
    assert opts[0]["payment"]["mode"] == "cashless"
    assert opts[0]["id"] == "org-gastro-2"


def test_in_network_non_cashless_offers_reimbursement():
    opts = _gastro("plan-b")
    reimb = next(o for o in opts if o["id"] == "org-gastro-3")
    p = reimb["payment"]
    assert p["mode"] == "reimbursement"
    assert p["patient_upfront_aed"] == 450
    assert p["expected_reimbursement_aed"] == 405  # 90 %
    assert p["patient_net_cost_aed"] == 45
    assert reimb["reimbursement_guide"]["documents"]
    assert "claim" in reimb["reimbursement_guide"]["summary_en"]


def test_oon_excluded_unless_plan_reimburses_or_patient_opts_in():
    # Plan B does not reimburse out-of-network care.
    assert all(o["in_network"] for o in _gastro("plan-b"))
    # Plan A reimburses OON pay-and-claim for a self-pay-accepting provider.
    a = {o["id"]: o for o in _gastro("plan-a")}
    assert a["org-gastro-intl"]["payment"]["mode"] == "reimbursement"
    assert "org-gastro-oon" not in a  # provider does not accept self-pay
    # Plan C has no reimbursement; only an explicit self-pay opt-in shows the OON clinic.
    assert _gastro("plan-c") == []
    c = _gastro("plan-c", allow_self_pay=True)
    assert [o["payment"]["mode"] for o in c] == ["self_pay"]


def test_ranking_is_deterministic_and_cashless_beats_reimbursement_on_ties():
    tie = [
        {"id": "b", "specialty": "family_medicine", "network_id": "n", "cashless": False, "distance_km": 1, "earliest_days": 1},
        {"id": "a", "specialty": "family_medicine", "network_id": "n", "distance_km": 1, "earliest_days": 1},
    ]
    plan = {"network_id": "n", "reimbursement": {"in_network": True, "pct": 80}}
    first = score_options("gp_review", {"n"}, tie, "en", plan)
    assert [o["id"] for o in first] == ["a", "b"]
    assert first == score_options("gp_review", {"n"}, list(reversed(tie)), "en", plan)


def test_payment_path_none_for_plain_oon():
    assert payment_path(PLAN_B, {"network_id": "x"}, False) is None


def test_claim_state_machine_and_roles():
    path = payment_path(PLAN_B, {"cashless": False, "fee_aed": 300}, True)
    claim = new_claim({"id": "p", "name": "P"}, path, "Plan B")
    claim = advance_claim(claim, "documents_ready", actor_role="patient")
    assert all(d["provided"] for d in claim["documents"])
    claim = advance_claim(claim, "submitted", actor_role="patient")
    with pytest.raises(PermissionError):
        advance_claim(claim, "approved", actor_role="patient")
    with pytest.raises(ValueError):
        advance_claim(claim, "paid", actor_role="coordinator")
    claim = advance_claim(claim, "approved", actor_role="coordinator")
    claim = advance_claim(claim, "paid", actor_role="coordinator")
    assert claim["status"] == "paid"


def test_insurer_payment_options_skill_allowlisted():
    cashless = payment_options(plan_id="plan-b", provider_id="org-gastro-2", consent=True)
    assert cashless["cashless_available"] is True and cashless["reason_code"] == "CASHLESS"
    reimb = payment_options(plan_id="plan-b", provider_id="org-gastro-3", consent=True)
    assert reimb["reimbursement_available"] is True and reimb["reimbursement_pct"] == 90
    assert set(reimb) <= ALLOWED_FIELDS
    assert payment_options(plan_id="plan-b", provider_id="x", consent=False)["reason_code"] == "CONSENT_REQUIRED"
    ack = submit_claim(case_id="c1", plan_id="plan-b", provider_id="org-gastro-3", amount_aed=450, consent=True)
    assert ack["claim_reference"].startswith("DHI-CLM-")
    assert ack == submit_claim(case_id="c1", plan_id="plan-b", provider_id="org-gastro-3", amount_aed=450, consent=True)


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


@pytest.mark.asyncio
async def test_booking_reimbursement_option_opens_tracked_claim(orch):
    ledger, coord, db = orch
    fatima = DEMO_PATIENTS["fatima"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "pay-1",
            "patient_id": fatima["id"],
            "patient": fatima,
            "observation": obs_fit_positive(fatima["id"], "o-pay-1"),
        },
    )
    cid = case["case_id"]
    await coord.accept_ownership(db, cid, "human:gp")
    await coord.notify_patient(db, cid)
    case = await ledger.get_case(db, cid)
    tb = [q["correct"] for q in case["messages"][-1]["teachback"]]
    case = await coord.submit_teachback(db, cid, tb)
    assert case["options"][0]["payment"]["mode"] == "cashless"
    assert case["evidence"]["payment_options"]["reason_code"] == "CASHLESS"
    reimb = next(o for o in case["options"] if o["payment"]["mode"] == "reimbursement")

    case = await coord.book(db, cid, reimb["id"])
    claim = case["evidence"]["claim"]
    assert case["evidence"]["payment_mode"] == "reimbursement"
    assert claim["status"] == "not_started" and claim["amount_claimed_aed"] == 450

    case = await coord.update_claim(db, cid, status="documents_ready", actor="patient:fatima", actor_role="patient")
    case = await coord.update_claim(db, cid, status="submitted", actor="patient:fatima", actor_role="patient")
    assert case["evidence"]["claim"]["insurer_ack"]["claim_status"] == "received"
    with pytest.raises(PermissionError):
        await coord.update_claim(db, cid, status="approved", actor="patient:fatima", actor_role="patient")
    case = await coord.update_claim(db, cid, status="approved", actor="human:coordinator-sara", actor_role="coordinator")
    assert [h["status"] for h in case["evidence"]["claim"]["history"]] == ["documents_ready", "submitted", "approved"]


@pytest.mark.asyncio
async def test_cashless_booking_has_no_claim(orch):
    ledger, coord, db = orch
    fatima = DEMO_PATIENTS["fatima"]
    case = await coord.open_from_observation(
        db,
        {
            "idempotency_key": "pay-2",
            "patient_id": fatima["id"],
            "patient": fatima,
            "observation": obs_fit_positive(fatima["id"], "o-pay-2"),
        },
    )
    cid = case["case_id"]
    await coord.accept_ownership(db, cid, "human:gp")
    await coord.notify_patient(db, cid)
    case = await ledger.get_case(db, cid)
    case = await coord.submit_teachback(db, cid, [q["correct"] for q in case["messages"][-1]["teachback"]])
    case = await coord.book(db, cid, case["options"][0]["id"])
    assert case["evidence"]["payment_mode"] == "cashless"
    assert "claim" not in case["evidence"]
    with pytest.raises(ValueError):
        await coord.update_claim(db, cid, status="documents_ready", actor="patient:fatima", actor_role="patient")


def test_claim_route_open_to_patient_persona():
    from app.auth import write_role_allowed

    assert write_role_allowed("/cases/c1/claim", "patient")
    assert write_role_allowed("/cases/c1/claim", "coordinator")


def test_rationale_pluralises_days_in_both_languages():
    from agents.navigator.scoring import _days_ar, _days_en

    assert _days_en(1) == "1 day" and _days_en(3) == "3 days"
    assert _days_ar(1) == "يوم واحد" and _days_ar(2) == "يومين" and _days_ar(3) == "3 أيام" and _days_ar(14) == "14 يومًا"
