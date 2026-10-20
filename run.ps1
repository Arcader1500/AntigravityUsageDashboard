# Antigravity Telemetry Control Launcher
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

$venvPython = Join-Path $scriptDir ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Error "Virtual environment not found at .venv. Run 'uv venv' and install dependencies."
    exit 1
}

Write-Host "Launching Antigravity Mission Telemetry at http://127.0.0.1:8501 ..." -ForegroundColor Cyan
& $venvPython -m uvicorn app:app --host 127.0.0.1 --port 8501 --reload
