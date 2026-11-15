"""Load golden case YAML definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "benchmark" / "golden_cases"


def load_golden_cases() -> list[dict[str, Any]]:
    files = sorted(GOLDEN_DIR.glob("GC-*.yaml"))
    cases = []
    for path in files:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        data["_path"] = str(path)
        cases.append(data)
    return cases
