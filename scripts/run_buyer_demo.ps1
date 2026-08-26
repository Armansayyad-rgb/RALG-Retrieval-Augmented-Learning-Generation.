# RALG Engine - buyer demo launcher (Windows PowerShell)
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\run_buyer_demo.ps1
#
# Runs preflight checks, then launches the existing Gradio WebUI on
# http://127.0.0.1:7860. Downloads nothing; overwrites nothing.

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "============================================================"
Write-Host " RALG Engine - buyer demo preflight"
Write-Host "============================================================"

$pyCandidates = @(".venv\Scripts\python.exe", "python")
$py = $null
foreach ($candidate in $pyCandidates) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) { $py = $candidate; break }
}
if (-not $py) {
    Write-Host "[FAIL] No Python found. Install Python 3.10+, or create .venv first:" -ForegroundColor Red
    Write-Host "       python -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
    exit 1
}

& $py scripts\buyer_demo_preflight.py --docker
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[FAIL] Preflight failed. Fix the items above, then re-run." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "============================================================"
Write-Host " Preflight passed. Starting WebUI on http://127.0.0.1:7860"
Write-Host " Demo walkthrough: docs\BUYER_DEMO_GUIDE.md"
Write-Host " Press Ctrl+C to stop the server."
Write-Host "============================================================"

& $py -m webui.app
