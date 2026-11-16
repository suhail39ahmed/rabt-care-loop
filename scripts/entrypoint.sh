#!/bin/sh
# One image, three roles: the API (default), the KB ingestion job, and the demo insurer agent.
set -e
case "${RABT_ROLE:-api}" in
  ingest)
    exec uv run --no-sync python scripts/rag_ingest.py --from-blob --apply ;;
  insurer)
    exec uv run --no-sync uvicorn services.insurer_demo.app:app --host 0.0.0.0 --port "${PORT:-8000}" ;;
  *)
    exec uv run --no-sync uvicorn app.main:app --app-dir services/orchestrator --host 0.0.0.0 --port "${PORT:-8000}" ;;
esac
