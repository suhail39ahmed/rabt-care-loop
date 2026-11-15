$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONPATH = "services/orchestrator;services;."
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uv sync --extra dev
uv run uvicorn app.main:app --app-dir services/orchestrator --host 0.0.0.0 --port 8000
