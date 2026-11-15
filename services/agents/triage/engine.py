"""Deterministic triage rules engine — no eval()."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from agents.triage.normalize import normalize_observation

RULES_PATH = Path(__file__).parent / "rules" / "v1.yaml"


class TriageResult(BaseModel):
    urgency: str
    pathway: str
    rule_id: str
    rule_version: str


def _load_rules() -> dict[str, Any]:
    with RULES_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _match_op(op: str, left: Any, right: Any) -> bool:
    if left is None:
        return False
    if op == ">=":
        return float(left) >= float(right)
    if op == ">":
        return float(left) > float(right)
    if op == "<=":
        return float(left) <= float(right)
    if op == "<":
        return float(left) < float(right)
    if op == "eq":
        return str(left).strip().lower() == str(right).strip().lower()
    if op == "contains":
        return str(right).lower() in str(left).lower()
    return False


def triage_observation(obs: dict[str, Any]) -> TriageResult:
    """Classify an observation using versioned YAML rules."""
    obs = normalize_observation(obs)
    cfg = _load_rules()
    version = cfg.get("version", "unknown")
    code = ""
    coding = (obs.get("code") or {}).get("coding") or []
    if coding:
        code = coding[0].get("code", "")

    fields: dict[str, Any] = {
        "value": None,
        "value_text": None,
        "systolic": obs.get("systolic"),
        "diastolic": obs.get("diastolic"),
    }
    if "valueQuantity" in obs:
        fields["value"] = obs["valueQuantity"].get("value")
        # Standalone systolic LOINC: also treat valueQuantity as systolic
        if code in {"8480-6"} and fields["systolic"] is None:
            fields["systolic"] = fields["value"]
        if code in {"8462-4"} and fields["diastolic"] is None:
            fields["diastolic"] = fields["value"]
    if "valueString" in obs:
        fields["value_text"] = obs["valueString"]
    if "valueCodeableConcept" in obs:
        fields["value_text"] = (obs["valueCodeableConcept"].get("text")
                                or (obs["valueCodeableConcept"].get("coding") or [{}])[0].get("display"))

    for rule in cfg.get("rules", []):
        loincs = rule.get("loinc_any") or []
        if code and code not in loincs:
            continue
        field = rule.get("field", "value")
        if _match_op(rule["op"], fields.get(field), rule["value"]):
            return TriageResult(
                urgency=rule["urgency"],
                pathway=rule["pathway"],
                rule_id=rule["id"],
                rule_version=version,
            )

    default = cfg.get("default", {"urgency": "NEEDS_HUMAN", "pathway": "human_triage"})
    return TriageResult(
        urgency=default["urgency"],
        pathway=default["pathway"],
        rule_id="DEFAULT",
        rule_version=version,
    )


async def run(req: dict[str, Any]) -> dict[str, Any]:
    obs = req.get("inputs", {}).get("observation") or req.get("inputs", {})
    result = triage_observation(obs)
    transition = "Escalated" if result.urgency == "CRITICAL" else "AwaitingOwner"
    if result.urgency == "NEEDS_HUMAN":
        return {
            "case_id": req["case_id"],
            "step": "triage",
            "status": "needs_human",
            "proposed_transition": None,
            "outputs": result.model_dump(),
            "evidence_refs": [],
        }
    # From New path we go Triaged first; coordinator applies Escalated/AwaitingOwner next
    return {
        "case_id": req["case_id"],
        "step": "triage",
        "status": "ok",
        "proposed_transition": "Triaged",
        "outputs": {**result.model_dump(), "next_after_triaged": transition},
        "evidence_refs": [f"Observation/{obs.get('id', 'unknown')}"],
    }
