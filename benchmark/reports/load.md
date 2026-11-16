# Load test results (#66)

**Do not run against the hosted demo** (the script refuses Container Apps URLs unless `LOAD_ALLOW_REMOTE=1`).

## Command

```bash
# API local
uvicorn app.main:app --app-dir services/orchestrator --port 8000
python scripts/load_test.py --base-url http://127.0.0.1:8000 --n 50 --concurrency 5
```

## Example local run (illustrative)

| Field | Value |
|---|---|
| Machine | Windows desktop / local Docker |
| N | 50 |
| Concurrency | 5 |
| Throughput | ~15–40 rps (machine-dependent) |
| p50 | ~0.05–0.15 s |
| p95 | ~0.15–0.40 s |

Re-run and replace this table with your measured numbers before citing externally. Script exits non-zero if any ingest fails.
