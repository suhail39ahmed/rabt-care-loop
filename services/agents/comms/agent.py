"""Patient Comms — template-first, LLM optional, teach-back."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agents.common.guardrails import content_safe, no_diagnosis

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


async def draft_message(template_text: str, lang: str) -> tuple[str, bool]:
    """Return (text, used_llm). Falls back to template if Azure not configured or unsafe."""
    import os

    if not os.environ.get("AZURE_OPENAI_ENDPOINT"):
        return template_text, False
    try:
        # Optional Agent Framework path — skip if package missing
        from agent_framework import Agent
        from agent_framework.openai import OpenAIChatClient
        from azure.identity.aio import AzureCliCredential

        instructions = (
            "You rewrite an APPROVED template for a patient. Keep every fact. Never diagnose, "
            "never give treatment advice, never add numbers. Target reading level: simple. "
            f"Language: {lang}. Return only the message text."
        )
        async with AzureCliCredential() as cred:
            client = OpenAIChatClient(
                azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                model=os.environ.get("AZURE_OPENAI_MODEL", ""),
                credential=cred,
            )
            agent = Agent(client=client, instructions=instructions)
            result = await agent.run(template_text)
            text = str(result)
        if content_safe(text) and no_diagnosis(text):
            return text, True
        return template_text, False
    except Exception:
        return template_text, False


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
    base = render_template(tpl, lang, vars)
    text, used_llm = await draft_message(base, lang)
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
