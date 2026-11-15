"""Deterministic data-quality checks."""

from __future__ import annotations

from typing import Any

ALLOWED_UNITS = {
    "%",
    "mg/dL",
    "mmol/L",
    "mmHg",
    "ng/mL",
}


def check_observation(obs: dict[str, Any], siblings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    queries: list[str] = []
    vq = obs.get("valueQuantity")
    vs = obs.get("valueString")
    vcc = obs.get("valueCodeableConcept")
    if not vq and not vs and not vcc and obs.get("systolic") is None:
        queries.append("missing_value")
    if vq:
        if vq.get("value") is None:
            queries.append("missing_value")
        unit = vq.get("unit") or vq.get("code")
        if not unit:
            queries.append("missing_unit")
        elif unit not in ALLOWED_UNITS:
            queries.append(f"unit_not_allowed:{unit}")

    if siblings:
        code = ((obs.get("code") or {}).get("coding") or [{}])[0].get("code")
        for other in siblings:
            ocode = ((other.get("code") or {}).get("coding") or [{}])[0].get("code")
            if code and ocode == code and other.get("id") != obs.get("id"):
                a = (vq or {}).get("value")
                b = (other.get("valueQuantity") or {}).get("value")
                if a is not None and b is not None:
                    # contradictory if one normal-ish and one high for HbA1c illustrative
                    if abs(float(a) - float(b)) >= 2.0:
                        queries.append("contradictory_same_day")

    if queries:
        return {"ok": False, "queries": queries}
    return {"ok": True, "queries": []}


async def run(req: dict[str, Any]) -> dict[str, Any]:
    inputs = req.get("inputs", {})
    obs = inputs.get("observation") or inputs
    siblings = inputs.get("siblings") or []
    result = check_observation(obs, siblings)
    if not result["ok"]:
        return {
            "case_id": req["case_id"],
            "step": "data_quality",
            "status": "ok",
            "proposed_transition": "DataQuery",
            "outputs": result,
            "evidence_refs": [],
        }
    return {
        "case_id": req["case_id"],
        "step": "data_quality",
        "status": "ok",
        "proposed_transition": "Triaged",  # coordinator will run triage after DQ ok path via New→Triaged
        "outputs": {**result, "dq_passed": True},
        "evidence_refs": [],
    }
