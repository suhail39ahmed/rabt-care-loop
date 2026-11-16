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


def build_chat_url(provider: str, base: str, model: str) -> str:
    """Chat completions URL for an OpenAI-compatible base or an Azure OpenAI / APIM gateway base.

    Azure bases may be the account endpoint, the APIM gateway URL, `.../openai`, or a full
    `.../openai/deployments/<name>` path; all get the deployment path and `api-version`.
    """
    base = base.rstrip("/")
    if provider != "azure":
        return f"{base}/chat/completions"
    version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")
    if "/openai/deployments/" in base:
        return f"{base}/chat/completions?api-version={version}"
    if base.endswith("/openai"):
        return f"{base}/deployments/{model}/chat/completions?api-version={version}"
    return f"{base}/openai/deployments/{model}/chat/completions?api-version={version}"


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

    provider = (os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if provider in ("", "off"):
        # Legacy AZURE_OPENAI_* settings imply the Azure URL shape.
        provider = "azure" if os.environ.get("AZURE_OPENAI_ENDPOINT") else "openai_compatible"
    model = os.environ.get("LLM_MODEL") or os.environ.get("AZURE_OPENAI_MODEL") or ""
    base = (os.environ.get("LLM_BASE_URL") or os.environ.get("AZURE_OPENAI_ENDPOINT") or "").rstrip("/")
    key = os.environ.get("LLM_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY") or ""

    headers: dict[str, str] = {"Content-Type": "application/json"}
    url = build_chat_url(provider, base, model)
    if key:
        if provider == "azure":
            # Azure OpenAI and the APIM AI gateway both read the key from `api-key`.
            # No Bearer header: APIM in entra_jwt/both mode would reject a non-JWT bearer.
            headers["api-key"] = key
        else:
            headers["Authorization"] = f"Bearer {key}"

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
