"""Content safety, no-diagnosis lexicon, PII scrub (lexicon-first; Azure optional)."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable

NO_DIAGNOSIS_PATTERNS = [
    r"(?<!mean )\byou have (diabetes|cancer|hypertension)\b",  # "does not mean you have" is allowed
    r"\byou are diagnos(?:ed|is)\b",
    r"\bdiagnosed with\b",
    r"\bthis means you have\b",
    r"\bthis means cancer\b",
    r"لديك (سرطان|سكري)",
    r"أنت مصاب",
]

RED_FLAG_PATTERNS = [
    r"\bsuicid",
    r"\bkill myself\b",
    r"\bend my life\b",
    r"\bwant to die\b",
    r"\boverdose\b",
    r"\bchest pain\b",
    r"\b(?:cannot|can't|can not) breathe\b",
    r"\bheavy bleeding\b",
    r"\bbleeding (?:heavily|a lot|won't stop)\b",
    r"\bsevere (?:abdominal|stomach|belly) pain\b",
    r"\b(?:fainted|passed out|unconscious)\b",
    r"انتحار",
    r"أريد أن أموت",
    r"إنهاء حياتي",
    r"ألم (?:شديد )?في الصدر",
    r"لا أستطيع التنفس",
    r"نزيف شديد",
    r"ألم شديد في البطن",
    r"أغمي علي",
]

# Personal clinical questions the KB must never answer: route to a clinician callback instead.
CLINICIAN_PATTERNS = [
    r"\bdo i have (?:cancer|diabetes|a tumou?r|polyps?|hpv)\b",
    r"\bam i (?:dying|going to die)\b",
    r"\bis (?:it|this|my result) cancer\b",
    r"\b(?:should|can) i (?:stop|skip|change|double) (?:my )?(?:medicine|medication|insulin|dose|tablets|blood thinner)",
    r"\bhow much (?:insulin|medicine|medication)\b",
    r"\bdiagnose me\b",
    r"هل (?:عندي|لدي|أنا مصابة? ب) ?(?:ال)?(?:سرطان|سكري)",
    r"هل (?:أوقف|أغير) (?:دوائي|الدواء|الأنسولين)",
]


def no_diagnosis(text: str) -> bool:
    return not any(re.search(p, text, re.IGNORECASE) for p in NO_DIAGNOSIS_PATTERNS)


def has_red_flag(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in RED_FLAG_PATTERNS)


def needs_clinician(text: str) -> bool:
    """A personal diagnosis or medication question: a clinician must answer, not the KB."""
    return any(re.search(p, text, re.IGNORECASE) for p in CLINICIAN_PATTERNS)


def scrub_pii(text: str, tokens: dict[str, str] | None = None) -> str:
    """Scrub PII before text leaves Rabt (see agents.common.pii for the full list)."""
    from agents.common.pii import scrub

    return scrub(text, tokens).text


def content_safe(text: str, max_sev: int | None = None) -> bool:
    """True if text is safe for a patient.

    Lexicon first (no diagnosis, no red flags), then Azure AI Content Safety text:analyze when
    CONTENT_SAFETY_ENDPOINT is set. Fails closed: if the service errors, the caller uses the template.
    """
    if not no_diagnosis(text):
        return False
    if has_red_flag(text):
        return False
    from agents.common import content_safety

    if not content_safety.configured():
        return True
    limit = max_sev if max_sev is not None else int(os.environ.get("CS_MAX_SEVERITY", "2"))
    verdict = content_safety.analyze_text(text)
    if verdict is None:
        return False
    return verdict["max_severity"] <= limit


def grounded_numbers(message: str, allowed: Iterable[str | float | int]) -> bool:
    """Every decimal/integer in the message must appear in allowed inputs."""
    allowed_set = {str(a) for a in allowed}
    nums = re.findall(r"\d+(?:\.\d+)?", message)
    return all(n in allowed_set for n in nums)
