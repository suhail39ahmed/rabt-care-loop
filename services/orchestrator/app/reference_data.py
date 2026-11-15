"""Synthetic directory, plans, networks, slots (fictional — not real insurers)."""

from __future__ import annotations

PROVIDERS = [
    {
        "id": "org-fp-aisha",
        "name": "Dr Aisha — Family Medicine (Al Zahiyah)",
        "specialty": "family_medicine",
        "network_id": "net-plan-b",
        "distance_km": 3.2,
        "earliest_days": 1,
        "languages": ["ar", "en"],
    },
    {
        "id": "org-fp-ravi",
        "name": "Dr Khan — Family Medicine (Mussafah)",
        "specialty": "family_medicine",
        "network_id": "net-plan-c",
        "distance_km": 8.0,
        "earliest_days": 2,
        "languages": ["en", "hi"],
    },
    {
        "id": "org-gastro-1",
        "name": "Capital Gastro Clinic",
        "specialty": "gastroenterology",
        "network_id": "net-plan-a",
        "distance_km": 5.0,
        "earliest_days": 5,
        "languages": ["en", "ar"],
    },
    {
        "id": "org-gastro-2",
        "name": "Corniche Digestive Centre",
        "specialty": "gastroenterology",
        "network_id": "net-plan-b",
        "distance_km": 4.1,
        "earliest_days": 3,
        "languages": ["ar", "en"],
    },
    {
        "id": "org-gastro-oon",
        "name": "Out-of-Network Gastro (Demo)",
        "specialty": "gastroenterology",
        "network_id": "net-other",
        "distance_km": 2.0,
        "earliest_days": 1,
        "languages": ["en"],
        "self_pay_ok": False,
    },
    {
        "id": "org-gyn-1",
        "name": "Women's Health Unit — Demo",
        "specialty": "gynaecology",
        "network_id": "net-plan-b",
        "distance_km": 6.0,
        "earliest_days": 4,
        "languages": ["ar", "en"],
    },
    {
        "id": "org-breast-1",
        "name": "Breast Imaging Follow-up Unit",
        "specialty": "breast",
        "network_id": "net-plan-b",
        "distance_km": 7.0,
        "earliest_days": 6,
        "languages": ["en", "ar"],
    },
    {
        "id": "org-breast-2",
        "name": "Second Breast Centre (Capacity Backup)",
        "specialty": "breast",
        "network_id": "net-plan-b",
        "distance_km": 9.0,
        "earliest_days": 2,
        "languages": ["en"],
    },
]

PLANS = {
    "plan-a": {"name": "Demo Care Plan A (fictional)", "network_id": "net-plan-a"},
    "plan-b": {"name": "Demo Care Plan B (fictional)", "network_id": "net-plan-b"},
    "plan-c": {"name": "Demo Care Plan C (fictional)", "network_id": "net-plan-c"},
}

DEMO_PATIENTS = {
    "fatima": {
        "id": "pat-fatima",
        "name": "Fatima (synthetic)",
        "language": "ar",
        "age": 46,
        "sex": "female",
        "plan_id": "plan-b",
        "generalPractitioner": [
            {"reference": "Practitioner/gp-aisha", "display": "Dr Aisha (Family Physician)"}
        ],
    },
    "ravi": {
        "id": "pat-ravi",
        "name": "Ravi (synthetic)",
        "language": "en",
        "age": 38,
        "sex": "male",
        "plan_id": "plan-c",
        "generalPractitioner": [
            {"reference": "Practitioner/gp-khan", "display": "Dr Khan (Family Physician)"}
        ],
    },
    "omar": {
        "id": "pat-omar",
        "name": "Omar (synthetic)",
        "language": "en",
        "age": 58,
        "sex": "male",
        "plan_id": "plan-b",
        "generalPractitioner": [
            {"reference": "Practitioner/gp-aisha", "display": "Dr Aisha (Family Physician)"}
        ],
    },
}
