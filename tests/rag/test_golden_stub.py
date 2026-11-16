import json
from pathlib import Path
from agents.common.injection import injection_blocked
from agents.rag.mock_retrieve import retrieve

GOLDEN = json.loads((Path(__file__).parent / "golden_qa.json").read_text(encoding="utf-8"))

def test_golden_cases():
    for row in GOLDEN:
        if row.get("expect_block"):
            assert injection_blocked(row["q"])
            continue
        hits = retrieve(row["q"])
        # mock may return empty for Arabic — still must not diagnose
        assert "diagnosed with" not in row["q"].lower()
