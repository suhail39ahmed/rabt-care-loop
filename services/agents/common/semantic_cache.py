"""In-memory semantic cache stub for general KB answers (#100)."""
from __future__ import annotations

from typing import Any

_CACHE: dict[str, Any] = {}

def cache_key(question: str, *, language: str, index_version: str) -> str:
    return f"{language}|{index_version}|{question.strip().lower()}"

def get(key: str) -> Any | None:
    return _CACHE.get(key)

def set(key: str, value: Any) -> None:
    _CACHE[key] = value
