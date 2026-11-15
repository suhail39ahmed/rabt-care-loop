.PHONY: up test api web

api:
	PYTHONPATH=services/orchestrator:services:. uv run uvicorn app.main:app --app-dir services/orchestrator --host 0.0.0.0 --port 8000

web:
	cd apps/web && npm run dev

test:
	PYTHONPATH=services/orchestrator:services:. uv run pytest -q

up:
	docker compose up -d
