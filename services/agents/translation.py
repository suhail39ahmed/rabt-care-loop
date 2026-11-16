"""Live translation between a coordinator and a patient (EN <-> AR).

1. Approved glossary for the phrases coordinators use most: exact, instant, no model call.
2. AI on: the text is pseudonymized ([NAME_1], [PHONE_1] ... stay on our side), translated by the
   small model with the reviewed `translate` prompt (Prompt Shields + Content Safety run in the LLM
   client), checked, then the real values are put back. The result is always labelled AI-translated.
3. AI off or the output fails a check: nothing is invented; the UI asks for an interpreter.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from agents.common.guardrails import content_safe
from agents.common.pii import pseudonymize, restore

Lang = Literal["en", "ar"]
_AR = re.compile(r"[\u0600-\u06FF]")

GLOSSARY: dict[str, str] = {
    "Please book your follow-up this week.": "يرجى حجز موعد المتابعة هذا الأسبوع.",
    "Your result needs a follow-up test. It is not a diagnosis.": "نتيجتك تحتاج إلى فحص متابعة. هذا ليس تشخيصًا.",
    "Your visit is cashless: you pay nothing at the clinic.": "زيارتك بدون دفع نقدي: لن تدفع شيئًا في العيادة.",
    "You pay at the visit and we help you claim it back.": "تدفع عند الزيارة ونساعدك في استرداد المبلغ.",
    "Can you attend tomorrow?": "هل يمكنك الحضور غدًا؟",
    "Do you need transport to the clinic?": "هل تحتاج إلى وسيلة نقل إلى العيادة؟",
    "Your care team will call you today.": "سيتصل بك فريق الرعاية اليوم.",
    "Thank you, see you at your appointment.": "شكرًا لك، نراك في موعدك.",
}
_REVERSE = {v: k for k, v in GLOSSARY.items()}


def detect(text: str) -> Lang:
    return "ar" if _AR.search(text or "") else "en"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def glossary_lookup(text: str, target: Lang) -> str | None:
    t = _norm(text)
    table = GLOSSARY if target == "ar" else _REVERSE
    return table.get(t)


def _plausible(src: str, out: str, target: Lang, placeholders: list[str]) -> bool:
    if not out or not out.strip():
        return False
    if not 0.3 <= len(out) / max(len(src), 1) <= 3.5:
        return False
    if target == "ar" and not _AR.search(out):
        return False
    if target == "en" and len(_AR.findall(out)) > len(out) * 0.2:
        return False
    return all(ph in out for ph in placeholders) and content_safe(out)


async def translate(text: str, target: Lang | None = None) -> dict[str, Any]:
    text = (text or "").strip()[:2000]
    source = detect(text)
    target = target or ("en" if source == "ar" else "ar")
    base = {"source_lang": source, "target_lang": target}
    if not text:
        return {**base, "text": "", "method": "none", "label": None}
    if source == target:
        return {**base, "text": text, "method": "same_language", "label": None}

    hit = glossary_lookup(text, target)
    if hit:
        return {**base, "text": hit, "method": "glossary", "label": "Approved translation"}

    from agents.common.llm_client import chat_completion
    from agents.common.prompts import get_prompt

    pseudo = pseudonymize(text)
    prompt = get_prompt("translate")
    out = await chat_completion(
        system=f"{prompt.system}\nTranslate to: {'Arabic' if target == 'ar' else 'English'}.",
        user=pseudo.text,
        task="translate",
        temperature=prompt.temperature if prompt.temperature is not None else 0,
        max_tokens=prompt.max_tokens,
        prompt_ref=prompt.ref,
    )
    if out and _plausible(pseudo.text, out, target, list(pseudo.mapping)):
        return {**base, "text": restore(out.strip(), pseudo.mapping), "method": "ai", "label": "AI-translated", "prompt": prompt.ref}
    return {
        **base,
        "text": None,
        "method": "unavailable",
        "label": None,
        "note": "No safe translation available. Use an interpreter or the approved phrases.",
    }
