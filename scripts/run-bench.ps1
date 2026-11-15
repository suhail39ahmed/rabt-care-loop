$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
uv run python benchmark/run_bench.py --seed 42
Write-Host "Wrote benchmark/reports/report.md and report.json"
