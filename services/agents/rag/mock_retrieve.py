"""Mock RAG retrieve over data/kb (#92)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

KB = Path(__file__).resolve().parents[3] / "data" / "kb"

def retrieve(question: str, *, k: int = 3) -> list[dict[str, Any]]:
    hits = []
    q = (question or "").lower().split()
    if not KB.exists():
        return hits
    for path in sorted(KB.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        score = sum(1 for w in q if w in text.lower())
        if score:
            hits.append({"id": path.stem, "path": path.name, "text": text[:600], "score": score})
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:k]
