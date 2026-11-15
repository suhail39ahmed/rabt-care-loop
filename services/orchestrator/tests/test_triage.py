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


def test_bp_critical_demo_shape():
    r = triage_observation(
        {
            "code": {"coding": [{"code": "85354-9"}]},
            "systolic": 190,
            "diastolic": 100,
        }
    )
    assert r.urgency == "CRITICAL"
    assert r.rule_id == "BP-CRIT"


def test_bp_critical_fhir_panel_components():
    r = triage_observation(
        {
            "resourceType": "Observation",
            "code": {"coding": [{"system": "http://loinc.org", "code": "85354-9"}]},
            "component": [
                {
                    "code": {"coding": [{"system": "http://loinc.org", "code": "8480-6"}]},
                    "valueQuantity": {"value": 195, "unit": "mmHg"},
                },
                {
                    "code": {"coding": [{"system": "http://loinc.org", "code": "8462-4"}]},
                    "valueQuantity": {"value": 95, "unit": "mmHg"},
                },
            ],
        }
    )
    assert r.urgency == "CRITICAL"
    assert r.rule_id == "BP-CRIT"


def test_bp_critical_standalone_systolic_value_quantity():
    r = triage_observation(
        {
            "code": {"coding": [{"system": "http://loinc.org", "code": "8480-6"}]},
            "valueQuantity": {"value": 195, "unit": "mmHg", "code": "mm[Hg]"},
        }
    )
    assert r.urgency == "CRITICAL"
    assert r.rule_id == "BP-CRIT"


def test_bp_critical_diastolic_only():
    r = triage_observation(
        {
            "code": {"coding": [{"code": "85354-9"}]},
            "component": [
                {
                    "code": {"coding": [{"code": "8462-4"}]},
                    "valueQuantity": {"value": 125, "unit": "mmHg"},
                }
            ],
        }
    )
    assert r.urgency == "CRITICAL"
    assert r.rule_id == "BP-CRIT-DIA"


def test_bp_normal_panel_not_critical():
    r = triage_observation(
        {
            "code": {"coding": [{"code": "85354-9"}]},
            "component": [
                {"code": {"coding": [{"code": "8480-6"}]}, "valueQuantity": {"value": 128, "unit": "mmHg"}},
                {"code": {"coding": [{"code": "8462-4"}]}, "valueQuantity": {"value": 82, "unit": "mmHg"}},
            ],
        }
    )
    assert r.urgency != "CRITICAL"


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
