"""Per-task model routing with failover log (#101)."""
from __future__ import annotations
import logging
from dataclasses import dataclass

log = logging.getLogger("rabt.llm_router")

POLICY = {
    "comms_rewrite": "small",
    "rag_answer": "strong",
    "classify_concern": "small",
    "translate": "small",
}

MODELS = {"small": "gpt-4o-mini", "strong": "gpt-4o"}

@dataclass
class RouteDecision:
    task: str
    model: str
    tier: str

def route(task: str) -> RouteDecision:
    tier = POLICY.get(task, "small")
    model = MODELS[tier]
    log.info("route task=%s tier=%s model=%s", task, tier, model)
    return RouteDecision(task=task, model=model, tier=tier)
