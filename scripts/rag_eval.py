#!/usr/bin/env python3
"""Offline RAG evaluation: retrieval hit rate (hit@1, hit@3, MRR) and must-escalate checks.

Uses the local retriever (same approved-only and language filters as Azure AI Search) and the real answer
pipeline with AI off, so it runs anywhere without Azure. Exit code 1 if below the thresholds.

  python scripts/rag_eval.py [--json] [--min-hit3 0.9]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))
EVAL = ROOT / "data" / "kb_eval" / "rag_eval.yaml"


def run(path: Path = EVAL, k: int = 3) -> dict[str, Any]:
    os.environ.setdefault("AI_ENABLED", "false")
    from agents.common import semantic_cache
    from agents.rag.answer import answer
    from agents.rag.retrieve import local_search

    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    rows, never = [], set(spec.get("never_retrieve", []))
    for item in spec["retrieval"]:
        hits = [h["doc_id"] for h in local_search(item["q"], language=item["lang"], k=k)]
        rank = next((i + 1 for i, d in enumerate(hits) if d in item["expect"]), None)
        rows.append({"q": item["q"], "lang": item["lang"], "expect": item["expect"], "got": hits, "rank": rank,
                     "leaked_draft": bool(never & set(hits))})
    esc = []
    for item in spec["must_escalate"]:
        semantic_cache.clear()
        out = asyncio.run(answer(item["q"], language=item["lang"]))
        esc.append({"q": item["q"], "lang": item["lang"], "expected": item["method"], "got": out["method"],
                    "ok": out["method"] == item["method"] and bool(out.get("hand_off"))})

    def summary(sel: list[dict[str, Any]]) -> dict[str, Any]:
        n = len(sel) or 1
        return {"n": len(sel), "hit@1": round(sum(r["rank"] == 1 for r in sel) / n, 3),
                "hit@3": round(sum(r["rank"] is not None for r in sel) / n, 3),
                "mrr": round(sum(1 / r["rank"] for r in sel if r["rank"]) / n, 3)}

    return {
        "retrieval": summary(rows),
        "by_language": {lang: summary([r for r in rows if r["lang"] == lang]) for lang in sorted({r["lang"] for r in rows})},
        "drafts_leaked": sum(r["leaked_draft"] for r in rows),
        "escalation": {"n": len(esc), "pass_rate": round(sum(e["ok"] for e in esc) / (len(esc) or 1), 3)},
        "misses": [r for r in rows if r["rank"] is None],
        "escalation_failures": [e for e in esc if not e["ok"]],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--min-hit3", type=float, default=0.9)
    args = ap.parse_args()
    rep = run()
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        r = rep["retrieval"]
        print(f"retrieval  n={r['n']} hit@1={r['hit@1']} hit@3={r['hit@3']} mrr={r['mrr']}")
        for lang, s in rep["by_language"].items():
            print(f"  {lang:<3} n={s['n']} hit@1={s['hit@1']} hit@3={s['hit@3']} mrr={s['mrr']}")
        print(f"escalation n={rep['escalation']['n']} pass={rep['escalation']['pass_rate']}  drafts leaked={rep['drafts_leaked']}")
        for m in rep["misses"]:
            print(f"  MISS [{m['lang']}] {m['q']} -> {m['got']} (want {m['expect']})")
        for e in rep["escalation_failures"]:
            print(f"  ESCALATION FAIL [{e['lang']}] {e['q']} -> {e['got']}")
    ok = rep["retrieval"]["hit@3"] >= args.min_hit3 and rep["escalation"]["pass_rate"] == 1 and not rep["drafts_leaked"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
