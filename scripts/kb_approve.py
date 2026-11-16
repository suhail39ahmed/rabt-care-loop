#!/usr/bin/env python3
"""Human-approved learning loop helper (#96): move pending → kb with version stamp."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PENDING = ROOT / "data" / "kb" / "_pending"
KB = ROOT / "data" / "kb"

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("filename")
    ap.add_argument("--reviewer", required=True)
    args = ap.parse_args()
    src = PENDING / args.filename
    if not src.exists():
        raise SystemExit(f"missing {src}")
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    dst = KB / f"{src.stem}.v{stamp}{src.suffix}"
    text = src.read_text(encoding="utf-8")
    header = f"<!-- approved_by: {args.reviewer} at {stamp} -->\n"
    dst.write_text(header + text, encoding="utf-8")
    print(f"wrote {dst}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
