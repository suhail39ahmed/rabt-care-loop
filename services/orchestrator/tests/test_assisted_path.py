"""Senior / assisted path: 60+ flagged, phone call queued at notification, callback and caregiver with consent."""

from __future__ import annotations

from fastapi.testclient import TestClient

P = {"X-Rabt-Persona": "patient:fatima"}
C = {"X-Rabt-Persona": "human:coordinator-sara"}


def _client():
    from app.main import app

    return TestClient(app)


def test_senior_case_is_assisted_and_call_is_queued():
    with _client() as c:
        c.post("/demo/reset", headers=C)
        case = c.get("/cases/case-gc11-senior").json()
        assert case["evidence"]["assisted"] is True and case["evidence"]["age"] == 68
        assert case["evidence"]["reminder_channels"][0] == "call"
        assert case["state"] == "PatientNotified"
        q = c.get("/queue").json()
        assert any(i["case_id"] == "case-gc11-senior" and i["kind"] == "assisted_call" for i in q)
        fit = c.get("/cases/case-gc05-fit").json()
        assert fit["evidence"]["assisted"] is False


def test_callback_request_and_caregiver_need_consent():
    with _client() as c:
        c.post("/demo/reset", headers=C)
        r = c.post("/cases/case-gc11-senior/callback-request", json={"reason": "easy mode"}, headers=P)
        assert r.status_code == 200 and r.json()["evidence"]["callback_requested"]
        assert any(i["kind"] == "callback_request" for i in c.get("/queue").json())
        bad = c.post("/cases/case-gc11-senior/caregiver",
                     json={"name": "Mariam", "relation": "daughter", "phone_last4": "4567", "consent": False}, headers=P)
        assert bad.status_code == 400
        ok = c.post("/cases/case-gc11-senior/caregiver",
                    json={"name": "Mariam", "relation": "daughter", "phone_last4": "4567", "consent": True}, headers=P)
        cg = ok.json()["evidence"]["caregiver"]
        assert cg["phone_last4"] == "4567" and cg["consent"] is True
