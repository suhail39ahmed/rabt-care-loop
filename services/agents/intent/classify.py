"""Intent / concern classification — crisis check is always deterministic (#95)."""

from __future__ import annotations

import re
from typing import Any

from agents.common.guardrails import has_red_flag

CONCERN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("cost", re.compile(r"\b(cost|expensive|pay|insurance|تكلفة|غالي)\b", re.IGNORECASE)),
    ("fear", re.compile(r"\b(afraid|fear|scared|cancer|خوف|سرطان)\b", re.IGNORECASE)),
    ("time", re.compile(r"\b(busy|time|work|وقت|مشغول)\b", re.IGNORECASE)),
    ("transport", re.compile(r"\b(transport|distance|far|مواصلات|بعيد)\b", re.IGNORECASE)),
    ("language", re.compile(r"\b(language|arabic|english|لغة)\b", re.IGNORECASE)),
    ("distrust", re.compile(r"\b(wrong|mistake|error|خطأ|غلط)\b", re.IGNORECASE)),
]

APPROVED_SNIPPETS: dict[str, dict[str, str]] = {
    "cost": {
        "en": "Your care team can check coverage and estimate costs before you book. Ask the coordinator for a cost card.",
        "ar": "يمكن لفريق الرعاية التحقق من التغطية وتقدير التكلفة قبل الحجز.",
    },
    "fear": {
        "en": "A screening result is not a diagnosis. Your clinician will explain what the next check means.",
        "ar": "نتيجة الفحص ليست تشخيصاً. سيشرح طبيبك معنى الخطوة التالية.",
    },
    "time": {
        "en": "We can offer earlier or later slots, or an e-consult if your clinician agrees.",
        "ar": "يمكننا اقتراح مواعيد أبكر أو لاحقاً، أو استشارة إلكترونية بموافقة طبيبك.",
    },
    "transport": {
        "en": "We rank in-network options by distance and earliest slot when you open the navigator.",
        "ar": "نرتب الخيارات داخل الشبكة حسب المسافة وأقرب موعد.",
    },
    "language": {
        "en": "Messages are available in Arabic and English. Ask for another language if needed.",
        "ar": "الرسائل متوفرة بالعربية والإنجليزية.",
    },
    "distrust": {
        "en": "You can ask for a human callback. Every automated step is logged with a rule id for review.",
        "ar": "يمكنك طلب اتصال بشري. كل خطوة آلية مسجلة برقم قاعدة للمراجعة.",
    },
    "other": {
        "en": "Thank you for sharing. A coordinator can call you or help you book.",
        "ar": "شكراً لمشاركتك. يمكن للمنسق الاتصال بك أو مساعدتك في الحجز.",
    },
    "crisis": {
        "en": "Please seek urgent medical help now. In the UAE call 998 for an ambulance or 999 for police, or go to the nearest emergency department. A member of our care team will also contact you.",
        "ar": "يرجى طلب المساعدة الطبية العاجلة الآن. في الإمارات اتصل بالرقم 998 للإسعاف أو 999 للشرطة، أو توجه إلى أقرب قسم طوارئ. سيتواصل معك أيضاً أحد أعضاء فريق الرعاية.",
    },
}


def classify_concern(text: str, *, language: str = "en") -> dict[str, Any]:
    if has_red_flag(text):
        return {
            "intent": "crisis",
            "crisis": True,
            "confidence": 1.0,
            "method": "deterministic_lexicon",
            "snippet": APPROVED_SNIPPETS["crisis"].get(language) or APPROVED_SNIPPETS["crisis"]["en"],
        }
    for name, pat in CONCERN_PATTERNS:
        if pat.search(text or ""):
            return {
                "intent": name,
                "crisis": False,
                "confidence": 0.8,
                "method": "deterministic_rules",
                "snippet": APPROVED_SNIPPETS[name].get(language) or APPROVED_SNIPPETS[name]["en"],
            }
    return {
        "intent": "other",
        "crisis": False,
        "confidence": 0.5,
        "method": "deterministic_rules",
        "snippet": APPROVED_SNIPPETS["other"].get(language) or APPROVED_SNIPPETS["other"]["en"],
    }


LABELS = ("cost", "fear", "time", "transport", "language", "distrust", "other")


async def classify_concern_ai(text: str, *, language: str = "en") -> dict[str, Any]:
    """Rules first; the small model only labels messages the rules could not place.

    Crisis detection is always deterministic and never delegated to the model. The model's reply must be
    one of LABELS, anything else is treated as "other". With AI off this equals classify_concern().
    """
    base = classify_concern(text, language=language)
    if base["crisis"] or base["intent"] != "other":
        return base
    from agents.common.llm_client import chat_completion
    from agents.common.prompts import get_prompt

    prompt = get_prompt("classify_concern")
    label = await chat_completion(
        system=prompt.system,
        user=text,
        task="classify_concern",
        temperature=0,
        max_tokens=prompt.max_tokens,
        prompt_ref=prompt.ref,
    )
    label = (label or "").strip().strip(".").lower()
    if label not in LABELS or label == "other":
        return base
    return {
        "intent": label,
        "crisis": False,
        "confidence": 0.6,
        "method": "llm_small_after_rules",
        "prompt": prompt.ref,
        "snippet": APPROVED_SNIPPETS[label].get(language) or APPROVED_SNIPPETS[label]["en"],
    }
