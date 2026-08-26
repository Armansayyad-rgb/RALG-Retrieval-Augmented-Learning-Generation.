# RALG Engine - buyer demo launcher (Windows PowerShell)
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\run_buyer_demo.ps1
#
# Runs preflight checks (including bounded port selection), then launches the
# existing Gradio WebUI. Downloads nothing; overwrites nothing; never
# terminates other processes.

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

Write-Host "============================================================"
Write-Host " RALG Engine - buyer demo preflight"
Write-Host "============================================================"

# --- Python ---------------------------------------------------------------
$pyCandidates = @(".venv\Scripts\python.exe", "python")
$py = $null
foreach ($candidate in $pyCandidates) {
    if (Test-Path (Join-Path $ProjectRoot $candidate)) { $py = (Join-Path $ProjectRoot $candidate); break }
    elseif (Get-Command $candidate -ErrorAction SilentlyContinue) { $py = $candidate; break }
}
if (-not $py) {
    Write-Host "[FAIL] No Python found. Install Python 3.10+, or create .venv first:" -ForegroundColor Red
    Write-Host "       python -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
    exit 1
}

# --- Module path: make src importable WITHOUT the buyer setting anything ---
# `python -m webui.app` needs `src` on sys.path; app.py can only fix its own
# imports after it is found, so the launcher must provide the path up front.
$env:PYTHONPATH = (Join-Path $ProjectRoot "src")

# --- Preflight + port selection -------------------------------------------
$preflightJson = & $py scripts\buyer_demo_preflight.py --docker | Out-String
$preflight = $preflightJson | ConvertFrom-Json
Write-Host $preflightJson
if (-not $preflight.pass) {
    Write-Host ""
    Write-Host "[FAIL] Preflight failed. Fix the items above, then re-run." -ForegroundColor Red
    exit 1
}
if (-not $preflight.selected_port) {
    Write-Host ("[FAIL] No available port in allowed range 7860-7870. " +
        "Free one of those ports on 127.0.0.1 and re-run. This launcher never terminates other processes.") -ForegroundColor Red
    exit 1
}

$env:WEBUI_PORT = [string]$preflight.selected_port
Write-Host ""
Write-Host "============================================================"
Write-Host " Preflight passed. Starting WebUI at $($preflight.webui_url)"
if ([int]$env:WEBUI_PORT -ne 7860) {
    Write-Host " NOTE: default port 7860 was occupied; using allowed fallback port $($env:WEBUI_PORT)."
}
Write-Host " Demo walkthrough: docs\BUYER_DEMO_GUIDE.md"
Write-Host " Press Ctrl+C to stop the server."
Write-Host "============================================================"

& $py -m webui.app
