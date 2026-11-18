"""Small-model-first LLM routing with per-task token limits and failover (#101).

Rules (in order):
  1. Each task has a default tier: small (gpt-4.1-mini) for rewording, classification and translation;
     strong (gpt-4o) only for grounded RAG answers.
  2. A small-tier task escalates to strong when its input is longer than LLM_ROUTER_ESCALATE_CHARS
     (default 6000 characters), because the small model's answers degrade on long contexts.
  3. Each task has its own max_tokens and input cap (input is compressed and trimmed to the cap).
  4. Failover: if the chosen deployment fails after the gateway's own retries, the call is retried once
     on the other tier. The APIM backend pool additionally fails over between Azure OpenAI accounts.
Deployments come from LLM_MODEL_SMALL / LLM_MODEL_STRONG (Terraform sets chat-small / chat-strong).

Router mode (LLM_ROUTER_MODE):
  python (default) -> the rules above pick small or strong per task.
  azure            -> every chat task goes to the Azure OpenAI model router deployment
                      (LLM_MODEL_ROUTER, default `model-router`), which picks the model per prompt.
                      Per-task max_tokens and input caps still apply, and the Python choice is the
                      failover if the router deployment errors. Note: model router is only offered as
                      GlobalStandard / DataZoneStandard, so prompts may be processed outside the
                      deployment region; keep `python` where data residency matters.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

log = logging.getLogger("rabt.llm_router")


@dataclass(frozen=True)
class RoutePolicy:
    tier: str
    max_tokens: int
    max_input_chars: int
    cacheable: bool = False
    can_escalate: bool = True
    failover: bool = True


POLICY: dict[str, RoutePolicy] = {
    "comms_rewrite": RoutePolicy("small", 400, 4000),
    "classify_concern": RoutePolicy("small", 5, 1500, can_escalate=False),
    "translate": RoutePolicy("small", 400, 3000),
    "rag_answer": RoutePolicy("strong", 350, 9000, cacheable=True, can_escalate=False),
}
DEFAULT = RoutePolicy("small", 300, 3000)


@dataclass(frozen=True)
class RouteDecision:
    task: str
    tier: str
    model: str
    fallback_model: str | None
    max_tokens: int
    max_input_chars: int
    cacheable: bool
    reason: str


def deployment_for(tier: str) -> str:
    small = os.environ.get("LLM_MODEL_SMALL") or os.environ.get("LLM_MODEL") or os.environ.get("AZURE_OPENAI_MODEL") or ""
    strong = os.environ.get("LLM_MODEL_STRONG") or os.environ.get("AZURE_OPENAI_MODEL_STRONG") or small
    return strong if tier == "strong" else small


def router_mode() -> str:
    mode = (os.environ.get("LLM_ROUTER_MODE") or "python").strip().lower()
    return mode if mode in ("python", "azure") else "python"


def router_deployment() -> str:
    return (os.environ.get("LLM_MODEL_ROUTER") or "model-router").strip()


def route(task: str, input_chars: int = 0) -> RouteDecision:
    p = POLICY.get(task, DEFAULT)
    tier, reason = p.tier, "policy"
    limit = int(os.environ.get("LLM_ROUTER_ESCALATE_CHARS", "6000"))
    if tier == "small" and p.can_escalate and input_chars > limit:
        tier, reason = "strong", f"input>{limit}chars"
    model = deployment_for(tier)
    other = deployment_for("small" if tier == "strong" else "strong")
    fallback = other if p.failover and other and other != model else None
    if router_mode() == "azure":
        # Azure model router picks the model; the Python choice is the failover.
        tier, reason, fallback, model = "router", "azure_model_router", model or None, router_deployment()
    log.info("route task=%s tier=%s model=%s reason=%s", task, tier, model, reason)
    return RouteDecision(task, tier, model, fallback, p.max_tokens, p.max_input_chars, p.cacheable, reason)


def compress(text: str, max_chars: int) -> str:
    """Cheap prompt compression: collapse whitespace, drop repeated lines, trim at a sentence boundary."""
    seen: set[str] = set()
    lines = []
    for line in (text or "").splitlines():
        norm = " ".join(line.split())
        if not norm or norm.lower() in seen:
            continue
        seen.add(norm.lower())
        lines.append(norm)
    out = "\n".join(lines)
    if len(out) <= max_chars:
        return out
    cut = out[:max_chars]
    dot = max(cut.rfind(". "), cut.rfind(".\n"), cut.rfind("。"), cut.rfind("؟"), cut.rfind("? "))
    return cut[: dot + 1] if dot > max_chars * 0.6 else cut


def estimate_tokens(*texts: str) -> int:
    """Conservative estimate: ~3 characters per token (English is ~4, Arabic closer to 2-3)."""
    return sum(max(len(t or "") // 3, 1) for t in texts)
