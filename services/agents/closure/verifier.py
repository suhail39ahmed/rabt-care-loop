"""Evidence-gated closure verifier — target 0 false closures."""

from __future__ import annotations

from typing import Any


def verify_closure(evidence: dict[str, Any]) -> dict[str, Any]:
    missing: list[str] = []
    has_encounter = bool(evidence.get("attended_encounter"))
    has_outcome = bool(evidence.get("outcome_document") or evidence.get("outcome_note"))
    human_signoff = bool(evidence.get("human_reason_code") and evidence.get("human_signer"))
    if has_encounter and has_outcome:
        return {"closable": True, "closure_ok": True, "missing": [], "mode": "evidence"}
    if human_signoff:
        return {"closable": True, "closure_ok": True, "missing": [], "mode": "human"}
    if not has_encounter:
        missing.append("attended_encounter")
    if not has_outcome:
        missing.append("outcome_document")
    return {"closable": False, "closure_ok": False, "missing": missing, "mode": None}


async def run(req: dict[str, Any]) -> dict[str, Any]:
    evidence = req.get("inputs", {}).get("evidence") or {}
    result = verify_closure(evidence)
    if result["closable"]:
        return {
            "case_id": req["case_id"],
            "step": "closure",
            "status": "ok",
            "proposed_transition": "Closed",
            "outputs": {"evidence": result},
            "evidence_refs": [],
        }
    return {
        "case_id": req["case_id"],
        "step": "closure",
        "status": "ok",
        "proposed_transition": "Owned",  # bounce back when incomplete from ClosurePending
        "outputs": {"evidence": result, "blocked": True},
        "evidence_refs": [],
    }
