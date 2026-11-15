"""Content safety, no-diagnosis lexicon, PII scrub (lexicon-first; Azure optional)."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable

NO_DIAGNOSIS_PATTERNS = [
    r"\byou have (diabetes|cancer|hypertension)\b",
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
    r"\bchest pain\b",
    r"\bcannot breathe\b",
    r"انتحار",
]


def no_diagnosis(text: str) -> bool:
    return not any(re.search(p, text, re.IGNORECASE) for p in NO_DIAGNOSIS_PATTERNS)


def has_red_flag(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in RED_FLAG_PATTERNS)


def scrub_pii(text: str, tokens: dict[str, str] | None = None) -> str:
    out = text
    for real, token in (tokens or {}).items():
        out = out.replace(real, token)
    out = re.sub(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", "[PHONE]", out)
    return out


def content_safe(text: str, max_sev: int | None = None) -> bool:
    """Return True if text is safe. Uses Azure Content Safety when configured; else lexicon."""
    if not no_diagnosis(text):
        return False
    if has_red_flag(text):
        return False
    endpoint = os.environ.get("CONTENT_SAFETY_ENDPOINT", "").strip()
    if not endpoint:
        return True
    try:
        from azure.ai.contentsafety import ContentSafetyClient
        from azure.ai.contentsafety.models import AnalyzeTextOptions
        from azure.identity import DefaultAzureCredential

        max_sev = max_sev if max_sev is not None else int(os.environ.get("CS_MAX_SEVERITY", "2"))
        client = ContentSafetyClient(endpoint, DefaultAzureCredential())
        res = client.analyze_text(AnalyzeTextOptions(text=text))
        return all((c.severity or 0) <= max_sev for c in res.categories_analysis)
    except Exception:
        # Fail closed for LLM path: caller should fall back to template
        return False


def grounded_numbers(message: str, allowed: Iterable[str | float | int]) -> bool:
    """Every decimal/integer in the message must appear in allowed inputs."""
    allowed_set = {str(a) for a in allowed}
    nums = re.findall(r"\d+(?:\.\d+)?", message)
    return all(n in allowed_set for n in nums)
