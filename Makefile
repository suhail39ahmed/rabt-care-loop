.PHONY: up test api web golden bench

api:
	PYTHONPATH=services/orchestrator:services:. uv run uvicorn app.main:app --app-dir services/orchestrator --host 0.0.0.0 --port 8000

web:
	cd apps/web && npm run dev

test:
	PYTHONPATH=services/orchestrator:services:. uv run pytest -q

golden:
	PYTHONPATH=services/orchestrator:services:. uv run pytest tests/golden -q --tb=short
	@echo "See benchmark/reports/golden_results.md"

bench:
	uv run python benchmark/run_bench.py --seed 42

up:
	docker compose up -d
