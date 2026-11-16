"""Reassurance companion: grounded answers from the approved KB only (#93, #98)."""

from __future__ import annotations

from typing import Any

from agents.rag.answer import answer


async def run(req: dict[str, Any]) -> dict[str, Any]:
    inputs = req.get("inputs") or {}
    question = inputs.get("question") or ""
    lang = inputs.get("language") or "en"
    out = await answer(question, language=lang, pii_tokens=inputs.get("pii_tokens") or {})
    hand_off = bool(out.get("hand_off"))
    return {
        "case_id": req["case_id"],
        "step": "reassurance",
        "status": "needs_human" if hand_off else "ok",
        "proposed_transition": "HumanCallback" if hand_off else None,
        "outputs": out,
        "evidence_refs": [c["id"] for c in out.get("citations", [])],
    }
