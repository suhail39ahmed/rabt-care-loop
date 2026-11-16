"""Prompt-injection protection: deny-list first, then Azure Prompt Shields when configured (#104)."""

from __future__ import annotations

import re

DENY = [
    r"ignore .{0,40}instructions",
    r"disregard .{0,40}(rules|instructions)",
    r"system prompt",
    r"reveal (your|the) (system|hidden)",
    r"you are now",
    r"<\s*script",
    r"exfiltrat",
    r"تجاهل .{0,30}(التعليمات|الأوامر)",
]


def deny_listed(text: str) -> bool:
    return any(re.search(p, text or "", re.IGNORECASE) for p in DENY)


def injection_blocked(text: str, documents: list[str] | None = None) -> bool:
    """True if the text (or attached documents) must not reach a model.

    Deny-list always runs. Prompt Shields runs when AI is on and CONTENT_SAFETY_ENDPOINT is set (text only reaches a model then); if the service is
    configured but fails, we fail closed.
    """
    if deny_listed(text) or any(deny_listed(d) for d in documents or []):
        return True
    from agents.common import content_safety
    from agents.common.llm_client import ai_enabled

    if not ai_enabled() or not content_safety.configured():
        return False
    verdict = content_safety.shield_prompt(text, documents)
    return verdict is None or verdict
