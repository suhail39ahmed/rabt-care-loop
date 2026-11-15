$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONPATH = "services/orchestrator;services;."
uv run pytest tests/golden -q --tb=short
Write-Host "See benchmark/reports/golden_results.md"
