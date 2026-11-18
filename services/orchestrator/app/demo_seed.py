"""Seed demo scenarios and golden-case fixtures (synthetic only)."""

from __future__ import annotations

from typing import Any

from app.coordinator import Coordinator
from app.ledger import Ledger
from app.reference_data import DEMO_PATIENTS


def obs_hba1c(patient_id: str, value: float = 7.2, obs_id: str = "obs-hba1c-1") -> dict[str, Any]:
    return {
        "resourceType": "Observation",
        "id": obs_id,
        "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": "4548-4", "display": "HbA1c"}]},
        "subject": {"reference": f"Patient/{patient_id}"},
        "valueQuantity": {"value": value, "unit": "%", "system": "http://unitsofmeasure.org", "code": "%"},
    }


def obs_bp_critical(patient_id: str, systolic: int = 190, obs_id: str = "obs-bp-1") -> dict[str, Any]:
    return {
        "resourceType": "Observation",
        "id": obs_id,
        "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": "85354-9", "display": "Blood pressure panel"}]},
        "subject": {"reference": f"Patient/{patient_id}"},
        "systolic": systolic,
        "diastolic": 100,
        "valueQuantity": {"value": systolic, "unit": "mmHg"},
    }


def obs_fit_positive(patient_id: str, obs_id: str = "obs-fit-1") -> dict[str, Any]:
    return {
        "resourceType": "Observation",
        "id": obs_id,
        "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": "2335-8", "display": "FIT"}]},
        "subject": {"reference": f"Patient/{patient_id}"},
        "valueString": "positive",
    }


def obs_glucose_bad_unit(patient_id: str, obs_id: str = "obs-glu-1") -> dict[str, Any]:
    return {
        "resourceType": "Observation",
        "id": obs_id,
        "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": "2339-0", "display": "Glucose"}]},
        "subject": {"reference": f"Patient/{patient_id}"},
        "valueQuantity": {"value": 180},  # missing unit
    }


def obs_mammo(patient_id: str, obs_id: str = "obs-mammo-1") -> dict[str, Any]:
    return {
        "resourceType": "Observation",
        "id": obs_id,
        "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": "24606-6", "display": "Mammography"}]},
        "subject": {"reference": f"Patient/{patient_id}"},
        "valueString": "BI-RADS 4",
    }


def obs_cervical(patient_id: str, obs_id: str = "obs-cerv-1") -> dict[str, Any]:
    return {
        "resourceType": "Observation",
        "id": obs_id,
        "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": "10524-7", "display": "Cervical cytology"}]},
        "subject": {"reference": f"Patient/{patient_id}"},
        "valueString": "abnormal",
    }


async def _book_seeded(ledger: Ledger, coordinator: Coordinator, db, case_id: str) -> bool:
    """Teach-back passed, then book the top option (pre-auth cleared). False if an insurer scenario blocks it."""
    case = await ledger.get_case(db, case_id)
    tb = []
    for m in reversed(case["messages"]):
        if m.get("teachback"):
            tb = [q["correct"] for q in m["teachback"]]
            break
    if tb:
        await coordinator.submit_teachback(db, case_id, tb)
    case = await ledger.get_case(db, case_id)
    opts = case.get("options") or []
    if not opts:
        return False
    evidence = dict(case.get("evidence") or {})
    cov = dict(evidence.get("coverage") or {})
    if cov.get("preauth_status") == "pending":
        cov["preauth_status"] = "approved"
        evidence["coverage"] = cov
        await ledger.update_case(db, case_id, evidence=evidence)
    try:
        await coordinator.book(db, case_id, opts[0]["id"])
        return True
    except ValueError as exc:
        await ledger.append_timeline(
            db, case_id, kind="fact", label="Seed booking skipped", detail=str(exc)[:120], actor="system:seed"
        )
        return False


async def _backdate(ledger: Ledger, db, case_id: str, seconds: float, **evidence_at: float) -> None:
    """Shift a seeded case back in time so the follow-up tracker has something to flag right after reset."""
    case = await ledger.get_case(db, case_id)
    prov = [{**p, "at": p["at"] - seconds} if p.get("at") else p for p in case["provenance"]]
    timeline = [{**t, "at": t["at"] - seconds} if t.get("at") else t for t in case["timeline"]]
    evidence = dict(case.get("evidence") or {})
    for k in ("attended_at", "appointment_at"):
        if evidence.get(k):
            evidence[k] = float(evidence[k]) - seconds
    evidence.update(evidence_at)
    await ledger.update_case(
        db, case_id, provenance=prov, timeline=timeline, evidence=evidence, created_at=case["created_at"] - seconds
    )


async def seed_demo(ledger: Ledger, coordinator: Coordinator) -> dict[str, str]:
    """Create named demo cases for guest mode. Returns map of scenario → case_id."""
    db = await ledger.connect()
    ids: dict[str, str] = {}

    # GC-01 / SC-01 — Fatima HbA1c (stable id for deck/README links)
    fatima = DEMO_PATIENTS["fatima"]
    c = await coordinator.open_from_observation(
        db,
        {
            "case_id": "case-gc01-fatima",
            "idempotency_key": "demo/GC-01",
            "patient_id": fatima["id"],
            "patient": fatima,
            "plan_id": fatima["plan_id"],
            "observation": obs_hba1c(fatima["id"], 7.2, "obs-gc01"),
        },
    )
    ids["gc01_fatima_hba1c"] = c["case_id"]
    await coordinator.accept_ownership(db, c["case_id"], "human:gp-aisha")
    await coordinator.notify_patient(db, c["case_id"])

    # GC-02 — critical BP
    omar = DEMO_PATIENTS["omar"]
    c2 = await coordinator.open_from_observation(
        db,
        {
            "case_id": "case-gc02-bp",
            "idempotency_key": "demo/GC-02",
            "patient_id": omar["id"],
            "patient": omar,
            "plan_id": omar["plan_id"],
            "observation": obs_bp_critical(omar["id"], 190, "obs-gc02"),
        },
    )
    ids["gc02_critical_bp"] = c2["case_id"]

    # GC-03 — AwaitingOwner for walkthrough step 2 (Dr Aisha accepts)
    c3 = await coordinator.open_from_observation(
        db,
        {
            "case_id": "case-gc03-owner",
            "idempotency_key": "demo/GC-03",
            "patient_id": omar["id"],
            "patient": omar,
            "plan_id": omar["plan_id"],
            "observation": obs_mammo(omar["id"], "obs-gc03"),
        },
    )
    ids["gc03_owner"] = c3["case_id"]

    # GC-05 — FIT positive for navigator (Plan C / Ravi)
    ravi = DEMO_PATIENTS["ravi"]
    c5 = await coordinator.open_from_observation(
        db,
        {
            "case_id": "case-gc05-fit",
            "idempotency_key": "demo/GC-05",
            "patient_id": ravi["id"],
            "patient": ravi,
            "plan_id": "plan-b",  # Plan B has gastro-2 in network; gastro-oon excluded
            "observation": obs_fit_positive(ravi["id"], "obs-gc05"),
        },
    )
    ids["gc05_fit"] = c5["case_id"]
    await coordinator.accept_ownership(db, c5["case_id"], "human:gp-khan")
    await coordinator.notify_patient(db, c5["case_id"])
    # pass teachback to get options
    case5 = await ledger.get_case(db, c5["case_id"])
    tb = []
    for m in reversed(case5["messages"]):
        if m.get("teachback"):
            tb = [q["correct"] for q in m["teachback"]]
            break
    if tb:
        await coordinator.submit_teachback(db, c5["case_id"], tb)

    # GC-07 — missing unit
    c7 = await coordinator.open_from_observation(
        db,
        {
            "case_id": "case-gc07-data",
            "idempotency_key": "demo/GC-07",
            "patient_id": omar["id"],
            "patient": omar,
            "observation": obs_glucose_bad_unit(omar["id"], "obs-gc07"),
        },
    )
    ids["gc07_data_query"] = c7["case_id"]

    # GC-08 — consent withdraw scenario (cervical)
    c8 = await coordinator.open_from_observation(
        db,
        {
            "case_id": "case-gc08-consent",
            "idempotency_key": "demo/GC-08",
            "patient_id": fatima["id"],
            "patient": fatima,
            "observation": obs_cervical(fatima["id"], "obs-gc08"),
        },
    )
    ids["gc08_consent"] = c8["case_id"]
    await coordinator.accept_ownership(db, c8["case_id"], "human:gp-aisha")
    await coordinator.withdraw_consent(db, c8["case_id"])

    # GC-10 — open case for false-closure attempt (booked but not attended)
    c10 = await coordinator.open_from_observation(
        db,
        {
            "case_id": "case-gc10-closure",
            "idempotency_key": "demo/GC-10",
            "patient_id": omar["id"],
            "patient": omar,
            "observation": obs_hba1c(omar["id"], 6.8, "obs-gc10"),
        },
    )
    ids["gc10_closure"] = c10["case_id"]
    await coordinator.accept_ownership(db, c10["case_id"], "human:gp-aisha")
    await coordinator.notify_patient(db, c10["case_id"])
    case10 = await ledger.get_case(db, c10["case_id"])
    tb = []
    for m in reversed(case10["messages"]):
        if m.get("teachback"):
            tb = [q["correct"] for q in m["teachback"]]
            break
    if tb:
        await coordinator.submit_teachback(db, c10["case_id"], tb)
    case10 = await ledger.get_case(db, c10["case_id"])
    opts = case10.get("options") or []
    if opts:
        # Plan B demo coverage starts preauth-pending; clear so GC-10 can seed Booked.
        evidence = dict(case10.get("evidence") or {})
        cov = dict(evidence.get("coverage") or {})
        if cov.get("preauth_status") == "pending":
            cov["preauth_status"] = "approved"
            evidence["coverage"] = cov
            await ledger.update_case(db, c10["case_id"], evidence=evidence)
        try:
            await coordinator.book(db, c10["case_id"], opts[0]["id"])
        except ValueError as exc:
            # A forced insurer demo scenario (denied, out-of-network) must not break Reset demo.
            await ledger.append_timeline(
                db, c10["case_id"], kind="fact", label="Seed booking skipped", detail=str(exc)[:120],
                actor="system:seed",
            )

    # GC-11 — senior / assisted path: Saeed, 68, positive FIT, Arabic, phone-first outreach
    saeed = DEMO_PATIENTS["saeed"]
    c11 = await coordinator.open_from_observation(
        db,
        {
            "case_id": "case-gc11-senior",
            "idempotency_key": "demo/GC-11",
            "patient_id": saeed["id"],
            "patient": saeed,
            "plan_id": saeed["plan_id"],
            "observation": obs_fit_positive(saeed["id"], "obs-gc11"),
        },
    )
    ids["gc11_senior"] = c11["case_id"]
    await coordinator.accept_ownership(db, c11["case_id"], "human:gp-aisha")
    await coordinator.notify_patient(db, c11["case_id"])

    # GC-12 — follow-up tracker: visit attended three hours ago, outcome still missing (result delayed, overdue)
    mariam = DEMO_PATIENTS["mariam"]
    c12 = await coordinator.open_from_observation(
        db,
        {
            "case_id": "case-gc12-result",
            "idempotency_key": "demo/GC-12",
            "patient_id": mariam["id"],
            "patient": mariam,
            "plan_id": mariam["plan_id"],
            "observation": obs_hba1c(mariam["id"], 8.1, "obs-gc12"),
        },
    )
    ids["gc12_result_delayed"] = c12["case_id"]
    await coordinator.accept_ownership(db, c12["case_id"], "human:gp-khan")
    await coordinator.notify_patient(db, c12["case_id"])
    if await _book_seeded(ledger, coordinator, db, c12["case_id"]):
        await coordinator.mark_attended(db, c12["case_id"], note="Repeat HbA1c drawn at the clinic")
        await _backdate(ledger, db, c12["case_id"], 3 * 3600)

    # GC-13 — follow-up tracker: booked visit was yesterday and nobody recorded attendance (missed visit)
    joel = DEMO_PATIENTS["joel"]
    c13 = await coordinator.open_from_observation(
        db,
        {
            "case_id": "case-gc13-missed",
            "idempotency_key": "demo/GC-13",
            "patient_id": joel["id"],
            "patient": joel,
            "plan_id": joel["plan_id"],
            "observation": obs_fit_positive(joel["id"], "obs-gc13"),
        },
    )
    ids["gc13_missed_visit"] = c13["case_id"]
    await coordinator.accept_ownership(db, c13["case_id"], "human:gp-aisha")
    await coordinator.notify_patient(db, c13["case_id"])
    if await _book_seeded(ledger, coordinator, db, c13["case_id"]):
        from app import demo_clock

        await _backdate(ledger, db, c13["case_id"], 3 * 86400, appointment_at=demo_clock.now() - 20 * 3600)

    # Raise the follow-up flags (and their queue items) now rather than on the first background tick.
    await coordinator.followup_sweep(db)
    await db.close()
    return ids
