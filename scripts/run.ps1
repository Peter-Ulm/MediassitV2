# MediAssist — start backend + frontend together.
# Run from the repo root:    .\scripts\run.ps1
#
# Opens two new PowerShell windows (one for backend, one for frontend).
# Close them with Ctrl+C in each, or close the window.

$ErrorActionPreference = "Stop"
$repo = Resolve-Path "$PSScriptRoot\.."
Set-Location $repo

# Sanity: ensure .venv exists
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Error ".venv not found. Run .\scripts\setup.ps1 first."
    exit 1
}

# Sanity: ensure node_modules exists
if (-not (Test-Path ".\frontend\node_modules")) {
    Write-Error "frontend\node_modules not found. Run .\scripts\setup.ps1 first."
    exit 1
}

$backendCmd  = "cd `"$repo`"; .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir backend"
$frontendCmd = "cd `"$repo\frontend`"; `$env:VITE_API_BASE_URL='http://localhost:8000/api/v1'; npm run dev"

Write-Host "==> Launching backend on http://localhost:8000" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

Write-Host "==> Launching frontend on http://localhost:5173" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd

Write-Host ""
Write-Host "MediAssist is starting. Open http://localhost:5173 in your browser." -ForegroundColor Green
Write-Host "Health check: http://localhost:8000/api/v1/health"
