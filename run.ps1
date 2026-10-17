# Launcher for the Antigravity usage dashboard (Windows PowerShell).
# Uses the project's own .venv, binds to localhost only, and opens the browser.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "No virtual environment found at .venv" -ForegroundColor Yellow
    Write-Host "Create it once with:" -ForegroundColor Yellow
    Write-Host "  py -m venv .venv"
    Write-Host "  .venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

# Pick a free port starting at 8501 so a stale server never blocks startup.
$port = 8501
while ($port -lt 8520) {
    $busy = $null
    try { $busy = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop } catch { }
    if (-not $busy) { break }
    $port++
}

Write-Host "Starting Antigravity usage dashboard on http://127.0.0.1:$port" -ForegroundColor Cyan
& $py -m streamlit run app.py --server.address 127.0.0.1 --server.port $port --browser.gatherUsageStats false
if ($LASTEXITCODE -ne 0) {
    Write-Host "Dashboard exited with code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}
