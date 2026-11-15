"""E-consult packet builder — extractive summary with source links."""

from __future__ import annotations

from typing import Any


async def run(req: dict[str, Any]) -> dict[str, Any]:
    inputs = req.get("inputs", {})
    case = inputs.get("case") or {}
    statements = []
    if case.get("result_display"):
        statements.append(
            {
                "text": f"Screening result: {case.get('result_display')} = {case.get('result_value')} {case.get('result_unit') or ''}".strip(),
                "source": f"Observation/{case.get('result_code', 'unknown')}",
                "kind": "recorded_fact",
            }
        )
    if case.get("urgency"):
        statements.append(
            {
                "text": f"Triage urgency (rule-based): {case['urgency']}",
                "source": "CalculatedFinding/triage",
                "kind": "calculated",
            }
        )
    question = inputs.get("question") or "Does this patient need a specialty visit, or is asynchronous advice enough?"
    packet = {
        "label": "AI-generated e-consult packet — review before send",
        "question": question,
        "statements": statements,
        "options_for_specialist": ["accept", "advise_asynchronously", "needs_visit"],
    }
    return {
        "case_id": req["case_id"],
        "step": "econsult",
        "status": "ok",
        "proposed_transition": None,
        "outputs": {"packet": packet, "needs_clinician_review": True},
        "evidence_refs": [s["source"] for s in statements],
    }
