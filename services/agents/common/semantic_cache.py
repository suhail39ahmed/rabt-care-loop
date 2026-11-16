"""App-side answer cache for general KB questions (#100).

The APIM semantic cache (Redis + embeddings) is the shared, cross-replica cache in Azure. This small
in-process cache sits in front of it so repeated questions don't even reach the gateway, and works
locally. Entries are scoped by language and KB index version, never by patient, and only hold answers
built from approved KB text (no case data). Matching: exact normalised text, or embedding cosine
similarity >= SEMANTIC_CACHE_THRESHOLD when embeddings are available, else token overlap >= 0.85.
"""

from __future__ import annotations

import math
import os
import re
import time
from typing import Any

from agents.common import ai_metrics

_CACHE: dict[str, list[dict[str, Any]]] = {}
MAX_PER_SCOPE = 256


def _norm(q: str) -> str:
    return " ".join(re.findall(r"[\w\u0600-\u06FF]+", (q or "").lower()))


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a.split()), set(b.split())
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def scope(language: str, index_version: str) -> str:
    return f"{language}|{index_version}"


def lookup(question: str, *, scope_key: str, embedding: list[float] | None = None) -> Any | None:
    ttl = int(os.environ.get("SEMANTIC_CACHE_TTL", "3600"))
    threshold = float(os.environ.get("SEMANTIC_CACHE_THRESHOLD", "0.92"))
    q = _norm(question)
    now = time.time()
    best, best_score = None, 0.0
    for e in _CACHE.get(scope_key, []):
        if now - e["at"] > ttl:
            continue
        if e["q"] == q:
            best, best_score = e, 1.0
            break
        if embedding and e.get("emb"):
            s = _cos(embedding, e["emb"])
            if s >= threshold and s > best_score:
                best, best_score = e, s
        elif not embedding:
            s = _jaccard(q, e["q"])
            if s >= 0.85 and s > best_score:
                best, best_score = e, s
    ai_metrics.incr("app_cache_hit" if best else "app_cache_miss")
    return None if best is None else best["value"] | {"cache": {"layer": "app", "score": round(best_score, 3)}}


def store(question: str, value: dict[str, Any], *, scope_key: str, embedding: list[float] | None = None) -> None:
    rows = _CACHE.setdefault(scope_key, [])
    rows.append({"q": _norm(question), "value": value, "emb": embedding, "at": time.time()})
    del rows[:-MAX_PER_SCOPE]


def clear() -> None:
    _CACHE.clear()


# Backwards-compatible helpers
def cache_key(question: str, *, language: str, index_version: str) -> str:
    return f"{language}|{index_version}|{_norm(question)}"
