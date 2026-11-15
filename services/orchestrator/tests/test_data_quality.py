from agents.data_quality.checks import check_observation


def test_fhir_bp_panel_with_components_passes_dq():
    result = check_observation(
        {
            "resourceType": "Observation",
            "code": {"coding": [{"system": "http://loinc.org", "code": "85354-9"}]},
            "component": [
                {
                    "code": {"coding": [{"code": "8480-6"}]},
                    "valueQuantity": {"value": 195, "unit": "mmHg"},
                },
                {
                    "code": {"coding": [{"code": "8462-4"}]},
                    "valueQuantity": {"value": 95, "unit": "mmHg"},
                },
            ],
        }
    )
    assert result["ok"] is True
    assert result["queries"] == []


def test_standalone_systolic_value_quantity_passes_dq():
    result = check_observation(
        {
            "code": {"coding": [{"code": "8480-6"}]},
            "valueQuantity": {"value": 195, "unit": "mmHg", "code": "mm[Hg]"},
        }
    )
    assert result["ok"] is True
