# Contributing

## Setup

```bash
uv sync --extra dev
cd apps/web && npm ci --legacy-peer-deps
```

## Tests

```bash
# API / agents / golden
PYTHONPATH=services/orchestrator:services:. uv run pytest -q

# Web build
cd apps/web && npm run build

# E2E (API on :8000, web on :3000)
cd apps/web && npx playwright test
```

## Pull requests

- `main` is protected: open a PR; do not push directly.
- Prefer conventional commits (`feat`, `fix`, `docs`, `chore`, `test`).
- Reference issues with `Closes #N` when the PR fully satisfies acceptance.
- Keep PRs small and focused; wait for CI (`test`, `web`, `e2e`, `docker`) to go green.

## Data

Use only synthetic fixtures under `services/orchestrator` / `benchmark/golden_cases`. Never commit real clinical data.
