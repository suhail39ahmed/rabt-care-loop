"""Azure AI Content Safety over REST: text moderation and Prompt Shields.

CONTENT_SAFETY_ENDPOINT may be the APIM gateway (Terraform default; the gateway exposes only
`/contentsafety/text:analyze` and `/contentsafety/text:shieldPrompt` and authenticates to the service
with its managed identity) or a Content Safety resource endpoint for local testing.
Key: CONTENT_SAFETY_KEY, else LLM_API_KEY (the APIM subscription key), sent as Ocp-Apim-Subscription-Key.
Every call fails closed (returns None / "attack") so the caller falls back to approved templates.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from agents.common import ai_metrics

log = logging.getLogger("rabt.content_safety")
API_VERSION = os.environ.get("CONTENT_SAFETY_API_VERSION", "2024-09-01")


def configured() -> bool:
    return bool(os.environ.get("CONTENT_SAFETY_ENDPOINT", "").strip())


def _post(op: str, body: dict[str, Any]) -> dict[str, Any] | None:
    base = os.environ.get("CONTENT_SAFETY_ENDPOINT", "").strip().rstrip("/")
    key = os.environ.get("CONTENT_SAFETY_KEY") or os.environ.get("LLM_API_KEY") or ""
    url = f"{base}/contentsafety/text:{op}?api-version={API_VERSION}"
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Ocp-Apim-Subscription-Key"] = key
    try:
        r = httpx.post(url, json=body, headers=headers, timeout=float(os.environ.get("CS_TIMEOUT", "8")))
        r.raise_for_status()
        return r.json()
    except Exception as e:  # network, 4xx/5xx, bad JSON
        log.warning("content_safety_%s_failed: %s", op, type(e).__name__)
        ai_metrics.incr("content_safety_errors")
        return None


def analyze_text(text: str) -> dict[str, Any] | None:
    """Return {"max_severity": int, "categories": {...}} or None when the call failed."""
    data = _post("analyze", {"text": text[:10000], "outputType": "FourSeverityLevels"})
    if data is None:
        return None
    cats = {c.get("category"): int(c.get("severity") or 0) for c in data.get("categoriesAnalysis", [])}
    worst = max(cats.values(), default=0)
    if worst > int(os.environ.get("CS_MAX_SEVERITY", "2")):
        ai_metrics.incr("content_safety_blocks")
    return {"max_severity": worst, "categories": cats}


def shield_prompt(user_prompt: str, documents: list[str] | None = None) -> bool | None:
    """Prompt Shields. True = attack detected, False = clean, None = not configured / failed."""
    if not configured():
        return None
    data = _post("shieldPrompt", {"userPrompt": user_prompt[:10000], "documents": [d[:10000] for d in documents or []]})
    if data is None:
        return None
    attack = bool((data.get("userPromptAnalysis") or {}).get("attackDetected")) or any(
        bool(d.get("attackDetected")) for d in data.get("documentsAnalysis") or []
    )
    if attack:
        ai_metrics.incr("prompt_shield_blocks")
    return attack
