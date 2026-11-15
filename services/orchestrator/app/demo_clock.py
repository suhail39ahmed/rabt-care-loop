"""Demo clock — wall time plus a fast-forward offset for video / golden tests."""

from __future__ import annotations

import time

_offset_seconds: float = 0.0


def now() -> float:
    return time.time() + _offset_seconds


def offset_seconds() -> float:
    return _offset_seconds


def advance(minutes: float) -> float:
    global _offset_seconds
    _offset_seconds += float(minutes) * 60.0
    return _offset_seconds


def reset() -> None:
    global _offset_seconds
    _offset_seconds = 0.0
