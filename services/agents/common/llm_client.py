"""Provider-agnostic LLM client with global AI kill switch (#68, #105)."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

log = logging.getLogger("rabt.llm")


def ai_enabled() -> bool:
    raw = os.environ.get("AI_ENABLED", "false").strip().lower()
    return raw in ("1", "true", "yes", "on")


def llm_configured() -> bool:
    provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if provider in ("", "off"):
        # legacy azure env still counts when AI_ENABLED
        return bool(os.environ.get("AZURE_OPENAI_ENDPOINT") and os.environ.get("AZURE_OPENAI_MODEL"))
    model = os.environ.get("LLM_MODEL") or os.environ.get("AZURE_OPENAI_MODEL") or ""
    base = os.environ.get("LLM_BASE_URL") or os.environ.get("AZURE_OPENAI_ENDPOINT") or ""
    return bool(model and base)


async def chat_completion(
    *,
    system: str,
    user: str,
    temperature: float = 0.2,
    max_tokens: int = 400,
) -> str | None:
    """OpenAI-compatible chat. Returns None when AI is off or the call fails."""
    if not ai_enabled():
        log.info("ai_kill_switch: skipped LLM call")
        return None
    if not llm_configured():
        return None

    provider = (os.environ.get("LLM_PROVIDER") or "openai_compatible").strip().lower()
    model = os.environ.get("LLM_MODEL") or os.environ.get("AZURE_OPENAI_MODEL") or ""
    base = (os.environ.get("LLM_BASE_URL") or os.environ.get("AZURE_OPENAI_ENDPOINT") or "").rstrip("/")
    key = os.environ.get("LLM_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY") or ""

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
        if provider == "azure":
            headers["api-key"] = key

    url = f"{base}/chat/completions"
    if provider == "azure" and "openai.azure.com" in base and "/openai/deployments/" not in base:
        url = (
            f"{base}/openai/deployments/{model}/chat/completions"
            f"?api-version={os.environ.get('AZURE_OPENAI_API_VERSION', '2024-06-01')}"
        )

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        log.warning("llm_call_failed: %s", e)
        return None
