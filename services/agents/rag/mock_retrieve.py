"""Local KB retrieval (kept for older imports); see agents.rag.retrieve (#92)."""

from __future__ import annotations

from typing import Any

from agents.rag.retrieve import local_search


def retrieve(question: str, *, k: int = 3, language: str = "en") -> list[dict[str, Any]]:
    return local_search(question, language=language, k=k)
