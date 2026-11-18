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
        "id": "org-gastro-3",
        "name": "Al Reem Specialist Hospital (pay & claim)",
        "specialty": "gastroenterology",
        "network_id": "net-plan-b",
        "cashless": False,
        "fee_aed": 450,
        "distance_km": 3.0,
        "earliest_days": 2,
        "languages": ["ar", "en"],
    },
    {
        "id": "org-gastro-intl",
        "name": "Saadiyat International Clinic (out-of-network)",
        "specialty": "gastroenterology",
        "network_id": "net-other",
        "self_pay_ok": True,
        "fee_aed": 600,
        "distance_km": 6.5,
        "earliest_days": 1,
        "languages": ["en", "ar", "hi"],
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

# Payment rules (fictional): cashless at network providers, plus pay-and-claim reimbursement
# where the plan offers it. pct = share of the paid fee the insurer pays back.
PLANS = {
    "plan-a": {
        "name": "Demo Care Plan A (fictional)",
        "network_id": "net-plan-a",
        "cashless": True,
        "copay_pct": 0,
        "reimbursement": {"in_network": True, "out_of_network": True, "pct": 80, "claim_window_days": 30},
    },
    "plan-b": {
        "name": "Demo Care Plan B (fictional)",
        "network_id": "net-plan-b",
        "cashless": True,
        "copay_pct": 10,
        "reimbursement": {"in_network": True, "out_of_network": False, "pct": 90, "claim_window_days": 30},
    },
    "plan-c": {
        "name": "Demo Care Plan C (fictional)",
        "network_id": "net-plan-c",
        "cashless": True,
        "copay_pct": 20,
        "reimbursement": {"in_network": False, "out_of_network": False, "pct": 0, "claim_window_days": 0},
    },
}

DEMO_PATIENTS = {
    "saeed": {
        "id": "pat-saeed",
        "name": "Saeed (synthetic)",
        "name_ar": "سعيد",
        "language": "ar",
        "age": 68,
        "sex": "male",
        "plan_id": "plan-b",
        "generalPractitioner": [
            {"reference": "Practitioner/gp-aisha", "display": "Dr Aisha (Family Physician)"}
        ],
    },
    "fatima": {
        "id": "pat-fatima",
        "name": "Fatima (synthetic)",
        "name_ar": "فاطمة",
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
        "name_ar": "رافي",
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
        "name_ar": "عمر",
        "language": "en",
        "age": 58,
        "sex": "male",
        "plan_id": "plan-b",
        "generalPractitioner": [
            {"reference": "Practitioner/gp-aisha", "display": "Dr Aisha (Family Physician)"}
        ],
    },
}
