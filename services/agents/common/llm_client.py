"""Provider-agnostic LLM client: kill switch, PII scrub, Prompt Shields, routing, budget, metrics.

Order of operations for every call (#68, #99, #101, #104, #105):
  1. AI_ENABLED kill switch: off -> return None (callers use approved templates).
  2. PII scrub on the system and user text (agents.common.pii), always.
  3. Prompt Shields on untrusted input (patient text, documents), when configured.
  4. Router picks the deployment, max_tokens and input cap; input is compressed to the cap.
  5. Daily token budget check.
  6. Call through the APIM AI gateway (task + cache headers), fail over to the other tier once.
  7. Record tokens, cache hit/miss (x-rabt-cache header from APIM) and latency.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from agents.common import ai_metrics
from agents.common.llm_router import compress, estimate_tokens, route
from agents.common.pii import scrub

log = logging.getLogger("rabt.llm")

UNTRUSTED_INPUT_TASKS = frozenset({"rag_answer", "classify_concern", "translate"})


def ai_enabled() -> bool:
    raw = os.environ.get("AI_ENABLED", "false").strip().lower()
    return raw in ("1", "true", "yes", "on")


def llm_configured() -> bool:
    provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if provider in ("", "off"):
        # legacy azure env still counts when AI_ENABLED
        return bool(os.environ.get("AZURE_OPENAI_ENDPOINT") and os.environ.get("AZURE_OPENAI_MODEL"))
    model = os.environ.get("LLM_MODEL_SMALL") or os.environ.get("LLM_MODEL") or os.environ.get("AZURE_OPENAI_MODEL") or ""
    base = os.environ.get("LLM_BASE_URL") or os.environ.get("AZURE_OPENAI_ENDPOINT") or ""
    return bool(model and base)


def _provider() -> str:
    provider = (os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if provider in ("", "off"):
        # Legacy AZURE_OPENAI_* settings imply the Azure URL shape.
        provider = "azure" if os.environ.get("AZURE_OPENAI_ENDPOINT") else "openai_compatible"
    return provider


def _base() -> str:
    return (os.environ.get("LLM_BASE_URL") or os.environ.get("AZURE_OPENAI_ENDPOINT") or "").rstrip("/")


def _key() -> str:
    return os.environ.get("LLM_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY") or ""


def build_chat_url(provider: str, base: str, model: str, op: str = "chat/completions") -> str:
    """Chat/embeddings URL for an OpenAI-compatible base or an Azure OpenAI / APIM gateway base.

    Azure bases may be the account endpoint, the APIM gateway URL, `.../openai`, or a full
    `.../openai/deployments/<name>` path; all get the deployment path and `api-version`.
    """
    base = base.rstrip("/")
    if provider != "azure":
        return f"{base}/{op}"
    version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")
    if "/openai/deployments/" in base:
        return f"{base}/{op}?api-version={version}"
    if base.endswith("/openai"):
        return f"{base}/deployments/{model}/{op}?api-version={version}"
    return f"{base}/openai/deployments/{model}/{op}?api-version={version}"


def auth_headers(provider: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    key = _key()
    if key:
        if provider == "azure":
            # Azure OpenAI and the APIM AI gateway both read the key from `api-key`.
            # No Bearer header: APIM in entra_jwt/both mode would reject a non-JWT bearer.
            headers["api-key"] = key
        else:
            headers["Authorization"] = f"Bearer {key}"
    return headers


async def _post_chat(
    client: httpx.AsyncClient, provider: str, model: str, headers: dict[str, str], payload: dict[str, Any]
) -> httpx.Response:
    url = build_chat_url(provider, _base(), model)
    body = dict(payload, model=model)
    r = await client.post(url, headers=headers, json=body)
    r.raise_for_status()
    return r


async def chat_completion(
    *,
    system: str,
    user: str,
    task: str = "comms_rewrite",
    temperature: float = 0.2,
    max_tokens: int | None = None,
    pii_tokens: dict[str, str] | None = None,
    cache_scope: str | None = None,
    documents: list[str] | None = None,
    prompt_ref: str | None = None,
) -> str | None:
    """Return the model's text, or None when AI is off, blocked, over budget or the call failed."""
    if not ai_enabled():
        log.info("ai_kill_switch: skipped LLM call")
        ai_metrics.incr("kill_switch_skips", task=task)
        return None
    if not llm_configured():
        return None

    s_sys, s_user = scrub(system, pii_tokens), scrub(user, pii_tokens)
    docs = [scrub(d, pii_tokens).text for d in documents or []]
    redacted = s_sys.counts + s_user.counts
    if redacted:
        ai_metrics.incr("pii_redactions", sum(redacted.values()), task=task, types=",".join(sorted(redacted)))

    if task in UNTRUSTED_INPUT_TASKS:
        from agents.common.injection import injection_blocked

        if injection_blocked(s_user.text, docs):
            ai_metrics.incr("injection_blocks", task=task)
            return None

    decision = route(task, len(s_user.text) + sum(len(d) for d in docs))
    user_text = compress(s_user.text, decision.max_input_chars)
    if docs:
        user_text = user_text + "\n\nSources:\n" + "\n".join(f"[{i}] {d}" for i, d in enumerate(docs, 1))
        user_text = compress(user_text, decision.max_input_chars)
    out_cap = min(max_tokens or decision.max_tokens, decision.max_tokens)
    if ai_metrics.would_exceed(estimate_tokens(s_sys.text, user_text) + out_cap):
        ai_metrics.incr("budget_refusals", task=task)
        log.warning("llm_budget_exceeded task=%s", task)
        return None

    provider = _provider()
    headers = auth_headers(provider)
    headers["x-rabt-task"] = task
    if decision.cacheable and cache_scope:
        headers["x-rabt-cacheable"] = "true"
        headers["x-rabt-cache-scope"] = cache_scope
    if prompt_ref:
        headers["x-rabt-prompt"] = prompt_ref

    payload: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": s_sys.text},
            {"role": "user", "content": user_text},
        ],
        "temperature": temperature,
        "max_tokens": out_cap,
    }
    models = [decision.model] + ([decision.fallback_model] if decision.fallback_model else [])
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=float(os.environ.get("LLM_TIMEOUT", "30"))) as client:
        for i, model in enumerate(models):
            try:
                r = await _post_chat(client, provider, model, headers, payload)
            except Exception as e:
                log.warning("llm_call_failed task=%s model=%s err=%s", task, model, type(e).__name__)
                if i + 1 < len(models):
                    ai_metrics.incr("failovers", task=task, from_model=model, to_model=models[i + 1])
                    continue
                ai_metrics.incr("llm_errors", task=task)
                return None
            data = r.json()
            usage = data.get("usage") or {}
            cache = (r.headers.get("x-rabt-cache") or ("miss" if headers.get("x-rabt-cacheable") else "none")).lower()
            ai_metrics.record_usage(
                task=task,
                tier=decision.tier if i == 0 else "failover",
                deployment=model,
                prompt=int(usage.get("prompt_tokens") or 0),
                completion=int(usage.get("completion_tokens") or 0),
                cache=cache,
            )
            ai_metrics.incr("latency_ms_total", int((time.perf_counter() - started) * 1000))
            try:
                return str(data["choices"][0]["message"]["content"]).strip()
            except (KeyError, IndexError, TypeError):
                ai_metrics.incr("llm_errors", task=task)
                return None
    return None


async def embed(texts: list[str]) -> list[list[float]] | None:
    """Embeddings through the same gateway (deployment AZURE_OPENAI_EMBEDDING_DEPLOYMENT)."""
    if not ai_enabled() or not llm_configured():
        return None
    model = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT") or os.environ.get("LLM_EMBEDDING_MODEL") or ""
    if not model:
        return None
    provider = _provider()
    url = build_chat_url(provider, _base(), model, op="embeddings")
    headers = auth_headers(provider) | {"x-rabt-task": "embed"}
    clean = [scrub(t).text[:8000] for t in texts]
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(url, headers=headers, json={"input": clean, "model": model})
            r.raise_for_status()
            data = r.json()
        ai_metrics.record_usage(
            task="embed", tier="embedding", deployment=model,
            prompt=int((data.get("usage") or {}).get("prompt_tokens") or 0), completion=0, cache="none",
        )
        return [d["embedding"] for d in sorted(data["data"], key=lambda d: d.get("index", 0))]
    except Exception as e:
        log.warning("embed_failed err=%s", type(e).__name__)
        ai_metrics.incr("llm_errors", task="embed")
        return None
