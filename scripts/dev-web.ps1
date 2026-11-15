$ErrorActionPreference = "Stop"
Set-Location (Join-Path (Split-Path $PSScriptRoot -Parent) "apps\web")
if (-not (Test-Path node_modules)) { npm install }
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000"
npm run dev
