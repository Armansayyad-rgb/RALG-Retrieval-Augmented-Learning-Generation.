# RALG Engine - demonstration launcher (Windows PowerShell)
# Usage: powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1
#
# Runs preflight checks (including bounded port selection), then launches the
# FastAPI API server and Gradio WebUI. Downloads nothing; overwrites nothing;
# never terminates other processes. Fails fast on errors, uses bounded readiness
# retries, and tracks child processes for cleanup.

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

Write-Host "--- Stage 1: Python discovery ---"
$pyCandidates = @(
    (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
    (Join-Path $ProjectRoot ".\python.exe"),
    "python"
)
$py = $null
foreach ($candidate in $pyCandidates) {
    if (Test-Path $candidate) {
        $py = $candidate
        Write-Host "Using Python: $py"
        break
    }
    elseif (Get-Command $candidate -ErrorAction SilentlyContinue) {
        $py = $candidate
        Write-Host "Using system Python: $py"
        break
    }
}
if (-not $py) {
    Write-Host "[FAIL] No Python found. Install Python 3.11, or create .venv first:" -ForegroundColor Red
    Write-Host "       python -m venv .venv; .venv\Scripts\Activate.ps1; python -m pip install -r requirements.txt"
    exit 1
}

$env:PYTHONPATH = (Join-Path $ProjectRoot "src")

Write-Host "--- Stage 2: Preflight + port selection ---"
$preflightJson = & $py scripts\demo_preflight.py --docker | Out-String
$preflight = $preflightJson | ConvertFrom-Json
Write-Host $preflightJson
if (-not $preflight.pass) {
    Write-Host "" -ForegroundColor Red
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
Write-Host "Preflight passed. Starting services at API port 8000, WebUI at $($preflight.webui_url)"
if ([int]$env:WEBUI_PORT -ne 7860) {
    Write-Host " NOTE: default port 7860 was occupied; using allowed fallback port $($env:WEBUI_PORT)."
}

Write-Host "--- Stage 3: Launch FastAPI API server ---"
Write-Host "Starting FastAPI on 127.0.0.1:8000 (background job)..."
$apiJob = Start-Job {
    & $py -m uvicorn src.api_server:app --host 127.0.0.1 --port 8000
}
Write-Host "FastAPI API server background job started (Job ID: $($apiJob.Id))"

Write-Host "--- Stage 4: Launch Gradio WebUI ---"
Write-Host "Starting Gradio WebUI on 127.0.0.1:$env:WEBUI_PORT (background)..."
$webuiJob = Start-Job {
    & $py -m webui_bootstrap
}
Write-Host "Gradio WebUI background job started (Job ID: $($webuiJob.Id))"

Write-Host "--- Stage 5: Readiness probe ---"
Write-Host "Probing FastAPI /ready on 127.0.0.1:8000 (up to 30s timeout)..."
$maxRetries = 30
$retryCount = 0
$ready = $false
while ($retryCount -lt $maxRetries) {
    try {
        $result = & $py -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=2)" -Timeout 10
        $ready = $true
        break
    } catch {
        $retryCount++
        Start-Sleep -Seconds 1
    }
}
if (-not $ready) {
    Write-Host "[WARN] Readiness probe did not complete after $maxRetries seconds. Services may still be starting up." -ForegroundColor Yellow
} else {
    Write-Host "Service ready after $retryCount retry(s)."
}

Write-Host "--- Stage 6: Status and Ctrl+C cleanup ---"
Write-Host ""
Write-Host "Both services are running."
Write-Host "  API (FastAPI):      http://127.0.0.1:8000  (common demo endpoints: /health, /ready, /ingest, /query)"
Write-Host "  WebUI (Gradio):     http://127.0.0.1:$env:WEBUI_PORT"
Write-Host "Press Ctrl+C to stop the services and exit."

function Ctrl+C {
    Write-Host ""
    Write-Host "Ctrl+C received. Stopping background jobs only..."
    Get-Job | Stop-Job -Force | Out-Null
    return
}

do {
    Start-Sleep -Seconds 1
} while ($true -and (-not $LastCtrlCTime))
