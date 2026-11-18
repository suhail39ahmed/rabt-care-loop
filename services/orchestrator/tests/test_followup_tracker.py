"""Follow-up tracker: time-in-step targets, follow-up flags, queue items and the ownership guarantee."""

from __future__ import annotations

from app import followup
from fastapi.testclient import TestClient

C = {"X-Rabt-Persona": "human:coordinator-sara"}
GP = {"X-Rabt-Persona": "human:gp-khan"}
P = {"X-Rabt-Persona": "patient:fatima"}


def _client():
    from app.main import app

    return TestClient(app)


def _flags(c, case_id: str) -> list[str]:
    return [f["flag"] for f in c.get(f"/cases/{case_id}").json()["followup"]["flags"]]


def _queue_kinds(c, case_id: str) -> list[str]:
    return [q["kind"] for q in c.get("/queue").json() if q["case_id"] == case_id]


def test_seeded_cases_show_every_flag_and_queue_items():
    with _client() as c:
        c.post("/demo/reset", headers=C)
        r = c.get("/followups").json()
        assert r["counts"]["missed_visit"] >= 1 and r["counts"]["result_delayed"] >= 1
        assert r["counts"]["overdue"] >= 1 and r["counts"]["unowned"] >= 1
        rows = {x["case_id"]: x for x in r["cases"]}
        assert {f["flag"] for f in rows["case-gc12-result"]["flags"]} >= {"result_delayed", "overdue"}
        assert [f["reason"] for f in rows["case-gc13-missed"]["flags"]] == ["past_appointment"]
        assert [f["flag"] for f in rows["case-gc07-data"]["flags"]] == ["unowned"]
        assert rows["case-gc12-result"]["owner_name"].startswith("Dr Khan")
        assert rows["case-gc12-result"]["time_in_state_s"] > rows["case-gc12-result"]["sla_s"]
        assert "followup_missed_visit" in _queue_kinds(c, "case-gc13-missed")
        assert "followup_result_delayed" in _queue_kinds(c, "case-gc12-result")
        labels = [t["label"] for t in c.get("/cases/case-gc13-missed").json()["timeline"]]
        assert "Follow-up flag: missed visit" in labels
        only = c.get("/followups?flag=missed_visit").json()["cases"]
        assert [x["case_id"] for x in only] == ["case-gc13-missed"]


def test_flags_raise_one_queue_item_per_appearance():
    with _client() as c:
        c.post("/demo/reset", headers=C)
        for _ in range(3):
            c.post("/demo/advance?minutes=1", headers=C)
        assert _queue_kinds(c, "case-gc13-missed").count("followup_missed_visit") == 1


def test_escalated_critical_case_always_has_an_owner():
    with _client() as c:
        c.post("/demo/reset", headers=C)
        case = c.get("/cases/case-gc02-bp").json()
        assert case["state"] == "Escalated"
        assert case["owner_id"] == followup.ON_CALL["owner_id"] and case["owner_name"] == "On-call supervisor"
        assigned = [t for t in case["timeline"] if t["label"] == "Owner assigned"]
        assert assigned and assigned[0]["actor"] == "system:followup"
        open_cases = [x for x in c.get("/cases").json() if x["state"] not in followup.CLOSED_STATES]
        unowned = [x["case_id"] for x in open_cases if not x["owner_id"]]
        assert unowned == ["case-gc07-data"]  # inside its grace period, flagged and queued


def test_taking_ownership_clears_unowned_and_its_queue_item():
    with _client() as c:
        c.post("/demo/reset", headers=C)
        assert "unowned" in _flags(c, "case-gc07-data")
        r = c.post("/cases/case-gc07-data/owner", headers=C)
        assert r.status_code == 200 and r.json()["owner_name"] == "Coordinator Sara"
        assert "unowned" not in _flags(c, "case-gc07-data")
        assert "followup_unowned" not in _queue_kinds(c, "case-gc07-data")
        labels = [t["label"] for t in r.json()["timeline"]]
        assert "Owner assigned" in labels and "Follow-up flag cleared: unowned" in labels


def test_reassign_and_permissions():
    with _client() as c:
        c.post("/demo/reset", headers=C)
        r = c.post("/cases/case-gc13-missed/owner", json={"owner": "human:gp-khan"}, headers=C)
        assert r.status_code == 200 and r.json()["owner_name"].startswith("Dr Khan")
        assert r.json()["timeline"][-1]["label"] in {"Owner reassigned", "Follow-up flag cleared: unowned"} or any(
            t["label"] == "Owner reassigned" for t in r.json()["timeline"]
        )
        assert c.post("/cases/case-gc13-missed/owner", headers=P).status_code == 403
        assert c.post("/cases/case-gc13-missed/owner", json={"owner": "human:nobody"}, headers=C).status_code == 400


def test_unowned_case_gets_the_coordinator_after_the_grace_period():
    with _client() as c:
        c.post("/demo/reset", headers=C)
        c.post("/demo/advance?minutes=31", headers=C)
        case = c.get("/cases/case-gc07-data").json()
        assert case["owner_name"] == "Coordinator Sara"
        flags = [f["flag"] for f in case["followup"]["flags"]]
        assert "unowned" not in flags and "result_delayed" in flags  # data query unresolved past its target


def test_tick_never_moves_or_closes_a_case():
    with _client() as c:
        c.post("/demo/reset", headers=C)
        before = {x["case_id"]: x["state"] for x in c.get("/cases").json()}
        for _ in range(4):
            c.post("/demo/advance?minutes=720", headers=C)
        after = {x["case_id"]: x["state"] for x in c.get("/cases").json()}
        assert after == before
        assert not [s for s in after.values() if s in followup.CLOSED_STATES]


def test_flagged_cases_still_reach_documented_closure():
    with _client() as c:
        c.post("/demo/reset", headers=C)
        # Result delayed: the outcome arrives, the loop closes on evidence, and the flags clear.
        r = c.post(
            "/cases/case-gc12-result/outcome",
            json={"outcome_ref": "Observation/hba1c-repeat-gc12", "outcome_note": "Repeat HbA1c reviewed"},
            headers=GP,
        )
        assert r.status_code == 200 and r.json()["state"] == "Closed"
        assert c.get("/followups").json()["counts"]["result_delayed"] == 0
        assert "followup_result_delayed" not in _queue_kinds(c, "case-gc12-result")
        # Missed visit: no-show reopens booking, the patient rebooks and attends, the outcome closes the loop.
        cid = "case-gc13-missed"
        assert c.post(f"/cases/{cid}/no-show", headers=C).json()["state"] == "Referred"
        assert [f["reason"] for f in c.get(f"/cases/{cid}").json()["followup"]["flags"] if f["flag"] == "missed_visit"] == [
            "rebook_pending"
        ]
        case = c.get(f"/cases/{cid}").json()
        opt = next(o for o in case["options"] if o.get("in_network"))
        assert c.post(f"/cases/{cid}/book", json={"option_id": opt["id"]}, headers=P).status_code == 200
        assert "missed_visit" not in _flags(c, cid)
        c.post(f"/cases/{cid}/attend", headers=C)
        r = c.post(f"/cases/{cid}/outcome", json={"outcome_ref": "DiagnosticReport/colonoscopy-gc13"}, headers=GP)
        assert r.json()["state"] == "Closed"
        assert c.get(f"/cases/{cid}").json()["followup"]["flags"] == []
        assert c.post(f"/cases/{cid}/owner", headers=C).status_code == 409


def test_compute_flags_rules_and_overrides(monkeypatch):
    now = 1_000_000.0
    base = {"owner_id": "x", "created_at": now - 10, "evidence": {}}
    assert followup.compute_flags({**base, "state": "Closed"}, now) == []
    noshow = followup.compute_flags({**base, "state": "NoShow", "provenance": [{"to": "NoShow", "at": now}]}, now)
    assert [f["flag"] for f in noshow] == ["missed_visit"]
    booked = {**base, "state": "Booked", "evidence": {"appointment_at": now - 2 * 3600}}
    assert [f["reason"] for f in followup.compute_flags(booked, now)] == ["past_appointment"]
    booked_future = {**base, "state": "Booked", "evidence": {"appointment_at": now + 3600}}
    assert followup.compute_flags(booked_future, now) == []
    owned = {**base, "state": "Owned", "provenance": [{"to": "Owned", "at": now - 61 * 60}]}
    assert [f["flag"] for f in followup.compute_flags(owned, now)] == ["overdue"]
    monkeypatch.setenv("RABT_FOLLOWUP_SLA_MINUTES", '{"Owned": 120}')
    assert followup.compute_flags(owned, now) == []
    assert [f["flag"] for f in followup.compute_flags({**base, "owner_id": None, "state": "Owned"}, now)] == ["unowned"]
    held = {**base, "state": "OnHoldConsent", "provenance": [{"to": "OnHoldConsent", "at": now - 10**6}]}
    assert followup.compute_flags(held, now) == []
