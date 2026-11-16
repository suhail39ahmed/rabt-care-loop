"""In-process AI counters, token usage and a daily token budget.

Every LLM/safety/cache event also goes to the `rabt.ai` logger with structured fields, which Azure
Monitor (App Insights) picks up when APPLICATIONINSIGHTS_CONNECTION_STRING is set. The counters back
GET /ai/metrics on the admin page. Values never include prompt text or PII, only counts.
"""

from __future__ import annotations

import logging
import os
import threading
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

log = logging.getLogger("rabt.ai")
_lock = threading.Lock()
_counters: Counter = Counter()
_tokens: dict[str, Counter] = defaultdict(Counter)  # by tier/deployment
_day = ""
_day_tokens = 0


def daily_budget() -> int:
    return int(os.environ.get("LLM_DAILY_TOKEN_BUDGET", "200000"))


def _roll_day() -> None:
    global _day, _day_tokens
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    if today != _day:
        _day, _day_tokens = today, 0


def incr(name: str, n: int = 1, **dims: Any) -> None:
    with _lock:
        _counters[name] += n
    log.info("ai_event", extra={"ai_event": name, "ai_count": n, **{f"ai_{k}": v for k, v in dims.items()}})


def budget_left() -> int:
    with _lock:
        _roll_day()
        return max(daily_budget() - _day_tokens, 0)


def would_exceed(estimated_tokens: int) -> bool:
    return estimated_tokens > budget_left()


def record_usage(*, task: str, tier: str, deployment: str, prompt: int, completion: int, cache: str) -> None:
    global _day_tokens
    with _lock:
        _roll_day()
        _day_tokens += prompt + completion
        t = _tokens[deployment]
        t["calls"] += 1
        t["prompt_tokens"] += prompt
        t["completion_tokens"] += completion
        _counters[f"cache_{cache}"] += 1
        _counters[f"task_{task}"] += 1
    log.info(
        "ai_usage",
        extra={
            "ai_event": "llm_call",
            "ai_task": task,
            "ai_tier": tier,
            "ai_deployment": deployment,
            "ai_prompt_tokens": prompt,
            "ai_completion_tokens": completion,
            "ai_cache": cache,
        },
    )


def snapshot() -> dict[str, Any]:
    with _lock:
        _roll_day()
        hits, misses = _counters.get("cache_hit", 0), _counters.get("cache_miss", 0)
        return {
            "counters": dict(_counters),
            "tokens_by_deployment": {k: dict(v) for k, v in _tokens.items()},
            "budget": {"day": _day, "used": _day_tokens, "limit": daily_budget(), "left": max(daily_budget() - _day_tokens, 0)},
            "cache_hit_rate": round(hits / (hits + misses), 3) if (hits + misses) else None,
        }


def reset() -> None:
    global _day_tokens
    with _lock:
        _counters.clear()
        _tokens.clear()
        _day_tokens = 0
