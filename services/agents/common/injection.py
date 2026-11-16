"""Prompt-injection protection — deny-list + optional shields hook (#104)."""

from __future__ import annotations

import os
import re

DENY = [
    r"ignore (all|previous) instructions",
    r"system prompt",
    r"reveal (your|the) (system|hidden)",
    r"<\s*script",
    r"exfiltrat",
]


def injection_blocked(text: str) -> bool:
    t = text or ""
    if any(re.search(p, t, re.I) for p in DENY):
        return True
    if os.environ.get("PROMPT_SHIELDS_ENDPOINT"):
        # Hook point for Azure Prompt Shields — deny-list still primary in demo
        return False
    return False
