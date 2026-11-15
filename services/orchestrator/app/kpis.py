"""Computed prototype KPIs — synthetic demo / benchmark only."""

from __future__ import annotations

from typing import Any


def _evidence(case: dict[str, Any]) -> dict[str, Any]:
    return dict(case.get("evidence") or {})


def has_closure_evidence(case: dict[str, Any]) -> bool:
    ev = _evidence(case)
    return bool(ev.get("attended_encounter") and ev.get("outcome_document"))


def has_two_person_override(case: dict[str, Any]) -> bool:
    ev = _evidence(case)
    if ev.get("two_person_approved"):
        return True
    if ev.get("approvers") and len(ev.get("approvers") or []) >= 2:
        return True
    return False


def is_false_closure(case: dict[str, Any]) -> bool:
    if case.get("state") not in {"Closed", "ClosedByHuman"}:
        return False
    if has_closure_evidence(case):
        return False
    if has_two_person_override(case):
        return False
    return True


def is_true_critical(case: dict[str, Any]) -> bool:
    ev = _evidence(case)
    if ev.get("ground_truth_critical") is True or case.get("ground_truth_critical") is True:
        return True
    return False


def was_escalated(case: dict[str, Any]) -> bool:
    if case.get("state") == "Escalated":
        return True
    for p in case.get("provenance") or []:
        if p.get("to") == "Escalated":
            return True
    return False


def compute_kpis(cases: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [c for c in cases if c.get("state") in {"Closed", "ClosedByHuman"}]
    false_closures = sum(1 for c in cases if is_false_closure(c))
    true_critical = [c for c in cases if is_true_critical(c)]
    escalated_critical = [c for c in true_critical if was_escalated(c)]
    recall = (len(escalated_critical) / len(true_critical)) if true_critical else 1.0
    return {
        "total_cases": len(cases),
        "closed": len(closed),
        "critical_total": len(true_critical),
        "critical_escalated": len(escalated_critical),
        "critical_escalation_recall": recall,
        "false_closures": false_closures,
        "states": {s: sum(1 for c in cases if c.get("state") == s) for s in {c.get("state") for c in cases}},
        "note": "Prototype KPIs on synthetic demo seed — not real-world outcomes.",
    }
