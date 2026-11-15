"""Deterministic escalation ladder — no LLM on this path."""

from __future__ import annotations

from typing import Any

# Placeholder delays in minutes (illustrative)
LADDER = [
    {"step": 1, "role": "coordinator", "delay_min": 0, "title": "Critical / breach — coordinator"},
    {"step": 2, "role": "physician", "delay_min": 15, "title": "Escalate to on-call physician"},
    {"step": 3, "role": "programme_lead", "delay_min": 45, "title": "Escalate to programme lead"},
]


def next_step(current: int = 0) -> dict[str, Any] | None:
    nxt = current + 1
    for item in LADDER:
        if item["step"] == nxt:
            return item
    return None


async def run(req: dict[str, Any]) -> dict[str, Any]:
    inputs = req.get("inputs", {})
    ladder_step = int(inputs.get("ladder_step") or 0)
    step = next_step(ladder_step)
    if not step:
        return {
            "case_id": req["case_id"],
            "step": "escalation",
            "status": "needs_human",
            "proposed_transition": None,
            "outputs": {"message": "ladder exhausted"},
            "evidence_refs": [],
        }
    # Critical SMS must NOT include result values
    message = {
        "channel": "sms",
        "text_en": "Please call the Rabt care line now. A clinician needs to speak with you.",
        "text_ar": "يرجى الاتصال بخط رعاية ربط الآن. يحتاج طبيب للتحدث معك.",
        "includes_values": False,
    }
    return {
        "case_id": req["case_id"],
        "step": "escalation",
        "status": "ok",
        "proposed_transition": "Escalated",
        "outputs": {"ladder": step, "safe_message": message, "llm_used": False},
        "evidence_refs": [],
    }
