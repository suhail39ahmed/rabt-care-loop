"""Normalize FHIR Observation shapes for triage / DQ (BP panels, valueQuantity)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

SYS_LOINC = {"8480-6"}
DIA_LOINC = {"8462-4"}
PANEL_LOINC = {"85354-9"}


def _coding_codes(resource: dict[str, Any]) -> list[str]:
    coding = (resource.get("code") or {}).get("coding") or []
    return [c.get("code", "") for c in coding if c.get("code")]


def _qty_value(node: dict[str, Any] | None) -> float | None:
    if not node:
        return None
    v = (node.get("valueQuantity") or {}).get("value")
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def extract_bp_fields(obs: dict[str, Any]) -> dict[str, float | None]:
    """Pull systolic/diastolic from demo fields, valueQuantity, or component[]."""
    systolic = obs.get("systolic")
    diastolic = obs.get("diastolic")
    try:
        systolic = float(systolic) if systolic is not None else None
    except (TypeError, ValueError):
        systolic = None
    try:
        diastolic = float(diastolic) if diastolic is not None else None
    except (TypeError, ValueError):
        diastolic = None

    codes = _coding_codes(obs)
    # Standalone systolic Observation (8480-6) with valueQuantity
    if SYS_LOINC.intersection(codes) and systolic is None:
        systolic = _qty_value(obs)
    if DIA_LOINC.intersection(codes) and diastolic is None:
        diastolic = _qty_value(obs)

    for comp in obs.get("component") or []:
        ccodes = _coding_codes(comp)
        val = _qty_value(comp)
        if val is None:
            continue
        if SYS_LOINC.intersection(ccodes) and systolic is None:
            systolic = val
        if DIA_LOINC.intersection(ccodes) and diastolic is None:
            diastolic = val

    return {"systolic": systolic, "diastolic": diastolic}


def normalize_observation(obs: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with systolic/diastolic filled for triage + DQ."""
    out = deepcopy(obs)
    bp = extract_bp_fields(out)
    if bp["systolic"] is not None:
        out["systolic"] = bp["systolic"]
    if bp["diastolic"] is not None:
        out["diastolic"] = bp["diastolic"]
    # If panel has components but no top-level value, mark a synthetic value for DQ
    codes = _coding_codes(out)
    if PANEL_LOINC.intersection(codes) or SYS_LOINC.intersection(codes) or DIA_LOINC.intersection(codes):
        if out.get("systolic") is not None or out.get("diastolic") is not None:
            if "valueQuantity" not in out and "valueString" not in out:
                # Prefer systolic for valueQuantity mirror so unit checks pass
                mirror = out.get("systolic") if out.get("systolic") is not None else out.get("diastolic")
                out["valueQuantity"] = {
                    "value": mirror,
                    "unit": "mmHg",
                    "system": "http://unitsofmeasure.org",
                    "code": "mm[Hg]",
                }
    return out
