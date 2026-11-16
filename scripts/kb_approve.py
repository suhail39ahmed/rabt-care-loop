#!/usr/bin/env python3
"""Clinician-approved learning loop from the command line (#96). Same rules as the API.

  python scripts/kb_approve.py list
  python scripts/kb_approve.py approve <id> --reviewer human:gp-aisha
  python scripts/kb_approve.py reject <id> --reviewer human:gp-aisha --reason "duplicate"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services"))

from agents.rag import kb


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["list", "approve", "reject"])
    ap.add_argument("id", nargs="?")
    ap.add_argument("--reviewer")
    ap.add_argument("--reason", default="")
    a = ap.parse_args()
    if a.action == "list":
        print(json.dumps([{k: p.get(k) for k in ("id", "title", "language", "suggested_by")} for p in kb.list_pending()],
                         ensure_ascii=False, indent=2))
        return 0
    if not a.id or not a.reviewer:
        ap.error("id and --reviewer are required")
    out = kb.approve(a.id, a.reviewer) if a.action == "approve" else kb.reject(a.id, a.reviewer, a.reason)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
