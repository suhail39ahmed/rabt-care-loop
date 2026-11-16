"""Patient Comms — template-first, LLM optional, teach-back."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agents.common.guardrails import content_safe, grounded_numbers, no_diagnosis, scrub_pii

TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "data" / "templates"


def load_template(result_class: str) -> dict[str, Any]:
    path = TEMPLATES_DIR / f"{result_class}.yaml"
    if not path.exists():
        path = TEMPLATES_DIR / "generic_urgent.yaml"
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def render_template(tpl: dict[str, Any], lang: str, vars: dict[str, str]) -> str:
    text = (tpl.get(lang) or tpl.get("en") or {}).get("body", "")
    for k, v in vars.items():
        text = text.replace("{" + k + "}", v)
    return text


def teachback_questions(tpl: dict[str, Any], lang: str) -> list[dict[str, Any]]:
    return (tpl.get(lang) or tpl.get("en") or {}).get("teachback", [])


async def draft_message(
    template_text: str,
    lang: str,
    *,
    pii_tokens: dict[str, str] | None = None,
    allowed_numbers: list[str | float | int] | None = None,
) -> tuple[str, bool]:
    """Return (text, used_llm). Falls back to template if AI off / unsafe (#68, #105)."""
    from agents.common.llm_client import chat_completion

    scrubbed_template = scrub_pii(template_text, pii_tokens)
    prompt = scrub_pii(scrubbed_template, pii_tokens)
    instructions = (
        "You rewrite an APPROVED template for a patient. Keep every fact. Never diagnose, "
        "never give treatment advice, never add numbers. Target reading level: simple. "
        f"Language: {lang}. Return only the message text."
    )
    try:
        result = await chat_completion(system=instructions, user=prompt)
        if not result:
            return scrubbed_template, False
        text = scrub_pii(str(result), pii_tokens)
        allowed = list(allowed_numbers or [])
        if allowed and not grounded_numbers(text, allowed):
            return scrubbed_template, False
        if content_safe(text) and no_diagnosis(text):
            return text, True
        return scrubbed_template, False
    except Exception:
        return scrubbed_template, False


async def run(req: dict[str, Any]) -> dict[str, Any]:
    inputs = req.get("inputs", {})
    if not inputs.get("consent_messaging", True):
        return {
            "case_id": req["case_id"],
            "step": "comms",
            "status": "needs_human",
            "proposed_transition": "OnHoldConsent",
            "outputs": {"blocked": "consent_withdrawn"},
            "evidence_refs": [],
        }

    lang = inputs.get("language") or "en"
    result_class = inputs.get("result_class") or "generic_urgent"
    low_literacy = bool(inputs.get("low_literacy"))
    if low_literacy and lang == "ar":
        result_class = f"{result_class}_simple" if (TEMPLATES_DIR / f"{result_class}_simple.yaml").exists() else result_class

    tpl = load_template(result_class)
    vars = {
        "first_name_token": inputs.get("first_name_token", "Patient"),
        "next_step": inputs.get("next_step", "book a follow-up visit"),
        "urgency": inputs.get("urgency", "URGENT"),
    }
    import re

    base = render_template(tpl, lang, vars)
    pii_tokens = inputs.get("pii_tokens") or {}
    # Only numbers present in the approved template may appear in LLM output
    allowed_nums = re.findall(r"\d+(?:\.\d+)?", base)
    text, used_llm = await draft_message(
        base, lang, pii_tokens=pii_tokens, allowed_numbers=allowed_nums
    )
    qs = teachback_questions(tpl, lang)

    return {
        "case_id": req["case_id"],
        "step": "comms",
        "status": "ok",
        "proposed_transition": "PatientNotified",
        "outputs": {
            "message": text,
            "language": lang,
            "used_llm": used_llm,
            "ai_generated": used_llm,
            "teachback": qs,
            "banner": "This is not a diagnosis" if lang == "en" else "هذا ليس تشخيصاً",
            "fact_vs_ai": {"recorded_facts": vars, "ai_text": text if used_llm else None},
        },
        "evidence_refs": [],
    }
