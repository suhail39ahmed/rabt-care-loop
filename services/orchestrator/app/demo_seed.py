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
        await coordinator.book(db, c10["case_id"], opts[0]["id"])

    await db.close()
    return ids
