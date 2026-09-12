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

Write-Host "--- Stage 1: Python discovery (Python 3.11 required) ---"

function Test-Python311 {
    param(
        [string]$PythonExe,
        [string[]]$PythonArgs = @()
    )
    if (-not $PythonExe) { return $false }
    try {
        $version = & $PythonExe @PythonArgs -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        return $version.Trim() -eq "3.11"
    } catch {
        return $false
    }
}

$pyExe = $null
$pyArgs = @()

$discoveryOrder = @(
    @{ exe = (Join-Path $ProjectRoot ".venv\Scripts\python.exe"); args = @() },
    @{ exe = (Join-Path $ProjectRoot "python.exe"); args = @() },
    @{ exe = "py"; args = @("-3.11") },
    @{ exe = "python"; args = @() }
)

foreach ($entry in $discoveryOrder) {
    $exe = $entry.exe
    $args = $entry.args

    if ($exe -eq "py") {
        if (-not (Get-Command py -ErrorAction SilentlyContinue)) { continue }
    }

    if (Test-Python311 $exe $args) {
        $pyExe = $exe
        $pyArgs = $args
        Write-Host "Using Python 3.11: $pyExe $($args -join ' ')"
        break
    }
}
if (-not $pyExe) {
    Write-Host "[FAIL] No Python 3.11 interpreter found." -ForegroundColor Red
    Write-Host "       This release requires Python 3.11 exactly (not 3.9, 3.10, or 3.12+)." -ForegroundColor Red
    Write-Host "       Install Python 3.11, or create .venv with Python 3.11:" -ForegroundColor Red
    Write-Host "       python3.11 -m venv .venv; .venv\Scripts\Activate.ps1; python -m pip install -r requirements.txt" -ForegroundColor Red
    exit 1
}

$env:PYTHONPATH = (Join-Path $ProjectRoot "src")

Write-Host "--- Stage 2: Preflight + port selection ---"
$preflightJson = & $pyExe @pyArgs scripts\demo_preflight.py --docker | Out-String
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
$apiJob = Start-Job -ArgumentList $pyExe, $pyArgs, $ProjectRoot {
    param($PythonExe, $PythonArgs, $Root)
    Set-Location $Root
    $env:PYTHONPATH = Join-Path $Root "src"
    & $PythonExe @PythonArgs -m uvicorn src.api_server:app --host 127.0.0.1 --port 8000
}
Write-Host "FastAPI API server background job started (Job ID: $($apiJob.Id))"

Write-Host "--- Stage 4: Launch Gradio WebUI ---"
Write-Host "Starting Gradio WebUI on 127.0.0.1:$env:WEBUI_PORT (background)..."
$webuiJob = Start-Job -ArgumentList $pyExe, $pyArgs, $ProjectRoot, $env:WEBUI_PORT {
    param($PythonExe, $PythonArgs, $Root, $WebUiPort)
    Set-Location $Root
    $env:PYTHONPATH = Join-Path $Root "src"
    $env:WEBUI_PORT = $WebUiPort
    & $PythonExe @PythonArgs -m webui_bootstrap
}
Write-Host "Gradio WebUI background job started (Job ID: $($webuiJob.Id))"

Write-Host "--- Stage 5: Readiness probe ---"
Write-Host "Probing FastAPI /ready on 127.0.0.1:8000 (up to 30s timeout)..."
$maxRetries = 30
$retryCount = 0
$ready = $false
while ($retryCount -lt $maxRetries) {
    try {
        # Use PowerShell-native probe for robustness; returns success only on HTTP 200
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/ready" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        # Silent retry; avoid printing tracebacks during ordinary startup window
        $retryCount++
        Start-Sleep -Seconds 1
    }
}

if (-not $ready) {
    Write-Host "[FAIL] Readiness probe failed after $maxRetries seconds. API server not ready." -ForegroundColor Red
    Write-Host "Inspecting API background job..."
    $apiStatus = Get-Job -Job $apiJob
    Write-Host "API Job State: $($apiStatus.State)"
    Write-Host "API Server Output:"
    Receive-Job -Job $apiJob
    Write-Host "Cleaning up jobs and exiting..."
    Get-Job | Stop-Job -Force | Out-Null
    exit 1
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
