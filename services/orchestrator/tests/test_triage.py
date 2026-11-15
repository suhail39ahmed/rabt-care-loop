from agents.triage.engine import triage_observation


def test_hba1c_urgent():
    r = triage_observation(
        {
            "code": {"coding": [{"code": "4548-4"}]},
            "valueQuantity": {"value": 7.1, "unit": "%"},
        }
    )
    assert r.urgency == "URGENT"
    assert r.rule_id == "HBA1C-HIGH"


def test_bp_critical():
    r = triage_observation(
        {
            "code": {"coding": [{"code": "85354-9"}]},
            "systolic": 190,
            "diastolic": 100,
        }
    )
    assert r.urgency == "CRITICAL"
    assert r.rule_id == "BP-CRIT"


def test_fit_positive():
    r = triage_observation(
        {
            "code": {"coding": [{"code": "2335-8"}]},
            "valueString": "positive",
        }
    )
    assert r.urgency == "URGENT"
    assert r.pathway == "specialist_gastro"


def test_unknown_needs_human():
    r = triage_observation(
        {
            "code": {"coding": [{"code": "99999-9"}]},
            "valueQuantity": {"value": 1, "unit": "%"},
        }
    )
    assert r.urgency == "NEEDS_HUMAN"
