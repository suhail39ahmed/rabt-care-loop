from app.kpis import compute_kpis, is_false_closure


def test_false_closure_seeded():
    cases = [
        {
            "case_id": "c1",
            "state": "Closed",
            "evidence": {},  # no attendance / outcome / override
            "provenance": [],
        },
        {
            "case_id": "c2",
            "state": "Closed",
            "evidence": {"attended_encounter": True, "outcome_document": True},
            "provenance": [],
        },
        {
            "case_id": "c3",
            "state": "ClosedByHuman",
            "evidence": {"two_person_approved": True, "approvers": ["a", "b"]},
            "provenance": [],
        },
    ]
    assert is_false_closure(cases[0]) is True
    assert is_false_closure(cases[1]) is False
    assert is_false_closure(cases[2]) is False
    k = compute_kpis(cases)
    assert k["false_closures"] == 1


def test_critical_recall_with_missed_case():
    cases = [
        {
            "case_id": "hit",
            "state": "Escalated",
            "evidence": {"ground_truth_critical": True},
            "provenance": [{"to": "Escalated"}],
        },
        {
            "case_id": "miss",
            "state": "AwaitingOwner",
            "urgency": "ROUTINE",
            "evidence": {"ground_truth_critical": True},
            "provenance": [{"to": "Triaged"}, {"to": "AwaitingOwner"}],
        },
    ]
    k = compute_kpis(cases)
    assert k["critical_total"] == 2
    assert k["critical_escalated"] == 1
    assert k["critical_escalation_recall"] == 0.5
