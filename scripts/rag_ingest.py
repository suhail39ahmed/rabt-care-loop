#!/usr/bin/env python3
"""Chunk + mock-embed approved KB sources (#94). Dry-run safe."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

KB = Path(__file__).resolve().parents[1] / "data" / "kb"

def chunk(text: str, size: int = 400) -> list[str]:
    return [text[i:i+size] for i in range(0, len(text), size)]

def embed(text: str) -> list[float]:
    h = hashlib.sha256(text.encode()).digest()
    return [b / 255.0 for b in h[:16]]

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    docs = []
    for path in sorted(KB.glob("*.md")):
        if path.parent.name.startswith("_"):
            continue
        for i, c in enumerate(chunk(path.read_text(encoding="utf-8"))):
            docs.append({"source": path.name, "chunk": i, "embedding": embed(c), "chars": len(c)})
    print(json.dumps({"chunks": len(docs), "dry_run": args.dry_run, "sample": docs[:1]}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
