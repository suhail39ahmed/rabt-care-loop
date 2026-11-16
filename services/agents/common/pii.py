"""Expanded UAE PII scrub (#99)."""

from __future__ import annotations

import re

from agents.common.guardrails import scrub_pii as base_scrub

EID = re.compile(r"\b784-?\d{4}-?\d{7}-?\d\b")
AR_NAME = re.compile(r"[\u0600-\u06FF]{2,}(?:\s+[\u0600-\u06FF]{2,})+")


def scrub_pii_uae(text: str, tokens: dict[str, str] | None = None) -> str:
    out = base_scrub(text, tokens)
    out = EID.sub("[EMIRATES_ID]", out)
    out = AR_NAME.sub("[AR_NAME]", out)
    return out
