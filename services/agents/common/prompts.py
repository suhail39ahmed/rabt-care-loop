"""Prompt registry: versioned, reviewed prompts in data/prompts/*.yaml.

Each file: id, version, task, reviewed (bool), reviewed_by, system, max_tokens, temperature.
Only reviewed prompts can be used; the highest version wins. Every LLM call records id@version and a
short sha256 of the text, so a message in the ledger can be traced to the exact prompt.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

PROMPTS_DIR = Path(os.environ.get("RABT_PROMPTS_DIR") or Path(__file__).resolve().parents[3] / "data" / "prompts")


class PromptNotApproved(LookupError):
    pass


@dataclass(frozen=True)
class Prompt:
    id: str
    version: str
    task: str
    system: str
    max_tokens: int | None
    temperature: float | None
    sha: str

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}#{self.sha}"


def _vkey(v: str) -> tuple[int, ...]:
    return tuple(int(p) if p.isdigit() else 0 for p in str(v).split("."))


@lru_cache
def _load() -> dict[str, list[tuple[dict, Path]]]:
    out: dict[str, list[tuple[dict, Path]]] = {}
    for path in sorted(PROMPTS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if "id" in data:
            out.setdefault(data["id"], []).append((data, path))
    return out


def get_prompt(prompt_id: str) -> Prompt:
    candidates = [d for d, _ in _load().get(prompt_id, []) if d.get("reviewed") is True]
    if not candidates:
        raise PromptNotApproved(f"no reviewed prompt for {prompt_id!r}")
    d = max(candidates, key=lambda x: _vkey(x.get("version", "0")))
    text = str(d.get("system") or d.get("text") or "").strip()
    return Prompt(
        id=d["id"],
        version=str(d.get("version")),
        task=str(d.get("task") or d["id"]),
        system=text,
        max_tokens=d.get("max_tokens"),
        temperature=d.get("temperature"),
        sha=hashlib.sha256(text.encode("utf-8")).hexdigest()[:12],
    )


def list_prompts() -> list[dict]:
    rows = []
    for pid, items in _load().items():
        for d, path in items:
            rows.append({"id": pid, "version": str(d.get("version")), "reviewed": d.get("reviewed") is True, "file": path.name})
    return sorted(rows, key=lambda r: (r["id"], _vkey(r["version"])))


def reload() -> None:
    _load.cache_clear()
