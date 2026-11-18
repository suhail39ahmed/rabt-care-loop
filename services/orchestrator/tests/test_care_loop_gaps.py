"""Care-loop gaps: missed appointments stay open, and insurer replies gate how a booking is paid."""

from __future__ import annotations

from fastapi.testclient import TestClient

P = {"X-Rabt-Persona": "patient:fatima"}
C = {"X-Rabt-Persona": "human:coordinator-sara"}


def _client():
    from app.main import app

    return TestClient(app)


def _book(c, case_id: str) -> None:
    case = c.get(f"/cases/{case_id}").json()
    opt = next(o for o in case["options"] if o.get("in_network"))
    assert c.post(f"/cases/{case_id}/book", json={"option_id": opt["id"]}, headers=P).status_code == 200


def test_no_show_reopens_booking_and_queues_follow_up():
    with _client() as c:
        c.post("/demo/reset", headers=C)
        cid = "case-gc10-closure"
        assert c.get(f"/cases/{cid}").json()["state"] == "Booked"
        r = c.post(f"/cases/{cid}/no-show", headers=C)
        assert r.status_code == 200
        case = r.json()
        assert case["state"] == "Referred" and case["evidence"]["no_shows"] == 1
        assert [p["to"] for p in case["provenance"]][-2:] == ["NoShow", "Referred"]
        kinds = [i["kind"] for i in c.get("/queue").json() if i["case_id"] == cid]
        assert "no_show_followup" in kinds and "callback_request" not in kinds

        _book(c, cid)
        case = c.post(f"/cases/{cid}/no-show", headers=C).json()
        assert case["evidence"]["no_shows"] == 2 and case["state"] != "Closed"
        kinds = [i["kind"] for i in c.get("/queue").json() if i["case_id"] == cid]
        assert "callback_request" in kinds


def test_no_show_is_clinician_only_and_needs_a_booking():
    with _client() as c:
        c.post("/demo/reset", headers=C)
        assert c.post("/cases/case-gc10-closure/no-show", headers=P).status_code == 403
        assert c.post("/cases/case-gc01-fatima/no-show", headers=C).status_code == 400


def test_unverified_coverage_never_promises_cashless():
    """A rejected or missing insurer reply books the visit but flags it for a person instead of saying cashless."""
    with _client() as c:
        c.post("/demo/reset", headers=C)
        cid = "case-gc05-fit"
        import asyncio

        from app import main

        async def set_cov():
            db = await main.ledger.connect()
            try:
                case = await main.ledger.get_case(db, cid)
                ev = dict(case["evidence"])
                ev["coverage"] = {"status": "error", "reason_code": "INSURER_REPLY_REJECTED"}
                await main.ledger.update_case(db, cid, evidence=ev)
            finally:
                await db.close()

        asyncio.run(set_cov())
        opt = next(o for o in c.get(f"/cases/{cid}").json()["options"] if (o.get("payment") or {}).get("mode") == "cashless")
        r = c.post(f"/cases/{cid}/book", json={"option_id": opt["id"]}, headers=P)
        assert r.status_code == 200
        assert r.json()["evidence"]["payment_mode"] == "unverified"
        assert any(i["kind"] == "coverage_unverified" for i in c.get("/queue").json() if i["case_id"] == cid)


def test_insurer_out_of_network_blocks_the_checked_clinic():
    with _client() as c:
        c.post("/demo/reset", headers=C)
        cid = "case-gc05-fit"
        import asyncio

        from app import main

        async def set_cov():
            db = await main.ledger.connect()
            try:
                case = await main.ledger.get_case(db, cid)
                ev = dict(case["evidence"])
                ev["coverage"] = {"status": "ok", "reason_code": "OUT_OF_NETWORK", "covered": False}
                await main.ledger.update_case(db, cid, evidence=ev)
                return ev["coverage_provider_id"]
            finally:
                await db.close()

        checked = asyncio.run(set_cov())
        r = c.post(f"/cases/{cid}/book", json={"option_id": checked}, headers=P)
        assert r.status_code == 400 and "out_of_network" in r.text
