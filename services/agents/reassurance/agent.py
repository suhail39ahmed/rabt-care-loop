"""Reassurance companion — RAG over approved KB only (local keyword search)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.common.guardrails import has_red_flag, no_diagnosis

KB_DIR = Path(__file__).resolve().parents[3] / "data" / "kb"


def search_kb(question: str, limit: int = 2) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    q = question.lower()
    if not KB_DIR.exists():
        return hits
    for path in sorted(KB_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        score = sum(1 for w in q.split() if w in text.lower())
        if score:
            hits.append({"id": path.stem, "path": str(path.name), "text": text[:800], "score": score})
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:limit]


async def run(req: dict[str, Any]) -> dict[str, Any]:
    question = (req.get("inputs") or {}).get("question") or ""
    lang = (req.get("inputs") or {}).get("language") or "en"
    if has_red_flag(question):
        return {
            "case_id": req["case_id"],
            "step": "reassurance",
            "status": "needs_human",
            "proposed_transition": "HumanCallback",
            "outputs": {
                "answer": (
                    "Please seek urgent medical help or contact emergency services if you are in danger."
                    if lang == "en"
                    else "يرجى طلب المساعدة الطبية العاجلة أو الاتصال بخدمات الطوارئ إذا كنت في خطر."
                ),
                "hand_off": True,
                "citations": [],
            },
            "evidence_refs": [],
        }

    chunks = search_kb(question)
    if not chunks:
        answer = (
            "I can only answer from our approved screening FAQ. Please ask your care team, or tap Talk to a person."
            if lang == "en"
            else "يمكنني الإجابة فقط من الأسئلة الشائعة المعتمدة. يرجى سؤال فريق الرعاية أو اضغط تحدث إلى شخص."
        )
        return {
            "case_id": req["case_id"],
            "step": "reassurance",
            "status": "ok",
            "proposed_transition": None,
            "outputs": {"answer": answer, "citations": [], "hand_off_offered": True},
            "evidence_refs": [],
        }

    # Extractive answer from first chunk — never diagnose
    body = chunks[0]["text"].split("\n", 2)[-1].strip()
    preface = (
        "Based on our approved FAQ (not a diagnosis): "
        if lang == "en"
        else "بناءً على الأسئلة الشائعة المعتمدة (وليس تشخيصاً): "
    )
    answer = preface + body[:500]
    if not no_diagnosis(answer):
        answer = (
            "A positive or abnormal screening result means more checks may be needed. It does not by itself mean you have a disease. Please follow the next step with your clinician."
        )
    return {
        "case_id": req["case_id"],
        "step": "reassurance",
        "status": "ok",
        "proposed_transition": None,
        "outputs": {
            "answer": answer,
            "citations": [{"id": c["id"], "path": c["path"]} for c in chunks],
            "hand_off_offered": True,
            "ai_generated": True,
        },
        "evidence_refs": [c["id"] for c in chunks],
    }
