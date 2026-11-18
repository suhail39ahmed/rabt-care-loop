"""Offline prompt-injection benchmark: app-layer deny-list on questions and on retrieved documents.

Run: uv run python benchmark/safety/run_safety.py
Writes benchmark/reports/safety.json and safety.md. Live layers (Prompt Shields through APIM and the gateway
llm-content-safety policy) are exercised by the deployed smoke test, not here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "services"), str(ROOT / "services" / "orchestrator")]

from agents.common.injection import deny_listed


def evaluate(case: dict) -> dict:
    q_hit = deny_listed(case["text"])
    d_hit = deny_listed(case.get("document", ""))
    blocked = q_hit or d_hit
    layer = "question deny-list" if q_hit else ("document deny-list" if d_hit else "-")
    outcome = "blocked" if blocked else "allowed"
    return {"id": case["id"], "kind": case["kind"], "lang": case["lang"], "expect": case["expect"],
            "outcome": outcome, "layer": layer, "pass": outcome == case["expect"]}


def run() -> dict:
    data = yaml.safe_load((ROOT / "benchmark" / "safety" / "cases.yaml").read_text(encoding="utf-8"))
    rows = [evaluate(c) for c in data["cases"]]
    attacks = [r for r in rows if r["expect"] == "blocked"]
    benign = [r for r in rows if r["expect"] == "allowed"]
    return {
        "label": data["label"],
        "cases": rows,
        "attack_block_rate": sum(r["outcome"] == "blocked" for r in attacks) / max(len(attacks), 1),
        "false_positive_rate": sum(r["outcome"] == "blocked" for r in benign) / max(len(benign), 1),
        "passed": sum(r["pass"] for r in rows),
        "total": len(rows),
    }


def render(report: dict) -> str:
    lines = ["# Prompt-injection benchmark (synthetic)", "", f"**Label:** {report['label']}", "",
             (f"Attacks blocked: **{report['attack_block_rate']:.0%}** · benign questions wrongly blocked: "
              f"**{report['false_positive_rate']:.0%}** · {report['passed']}/{report['total']} cases as expected."), "",
             "| Case | Kind | Lang | Expected | Outcome | Layer |", "| --- | --- | --- | --- | --- | --- |"]
    lines += [f"| {r['id']} | {r['kind']} | {r['lang']} | {r['expect']} | {r['outcome']} | {r['layer']} |"
              for r in report["cases"]]
    lines += ["", "Live layers on top of this: Prompt Shields (user prompt + documents) called by the app through APIM,",
              "then the APIM `llm-content-safety` policy (shield-prompt + harm categories) on every model call."]
    return "\n".join(lines) + "\n"


def main() -> int:
    report = run()
    out = ROOT / "benchmark" / "reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / "safety.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md = render(report)
    (out / "safety.md").write_text(md, encoding="utf-8")
    print(md)
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
