# RALG Engine - buyer demo launcher (Windows PowerShell)
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\run_buyer_demo.ps1
#
# Runs preflight checks (including bounded port selection), then launches the
# existing Gradio WebUI. Downloads nothing; overwrites nothing; never
# terminates other processes. Fail fast on errors, clearly separated stages,
# sensible timeout/retry for readiness, proper exit codes.

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

# --- Stage 1: Python discovery ---
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
    Write-Host "[FAIL] No Python found. Install Python 3.10+, or create .venv first:" -ForegroundColor Red
    Write-Host "       python -m venv .venv; .venv\Scripts\Activate.ps1; python -m pip install -r requirements.txt"
    exit 1
}

# --- Module path: make src importable ---
$env:PYTHONPATH = (Join-Path $ProjectRoot "src")

# --- Stage 2: Preflight + port selection ---
Write-Host "--- Stage 2: Preflight + port selection ---"
$preflightJson = & $py scripts\buyer_demo_preflight.py --docker | Out-String
$preflight = $preflightJson | ConvertFrom-Json
Write-Host $preflightJson
if (-not $preflight.pass) {
    Write-Host "" -ForegroundColor Red
    Write-Host "[FAIL] Preflight failed. Fix the items above, then re-run." -ForegroundColor Red
    exit 1
}
if (-not $preflight.selected_port) {
    Write-Host ("[FAIL] No available port in allowed range $($PORT_RANGE_START)-$($PORT_RANGE_END). " +
        "Free one of those ports on 127.0.0.1 and re-run. This launcher never terminates other processes.") -ForegroundColor Red
    exit 1
}

$env:WEBUI_PORT = [string]$preflight.selected_port
Write-Host ""
Write-Host "Preflight passed. Starting WebUI at $($preflight.webui_url)"
if ([int]$env:WEBUI_PORT -ne 7860) {
    Write-Host " NOTE: default port 7860 was occupied; using allowed fallback port $($env:WEBUI_PORT)."
}

# --- Stage 3: Launch WebUI ---
Write-Host "--- Stage 3: Launch WebUI ---"
Write-Host "Demo walkthrough: docs\BUYER_DEMO_GUIDE.md"
Write-Host "Press Ctrl+C to stop the server."

# --- Stage 4: Readiness probe with timeout ---
Write-Host "--- Stage 4: Readiness probe ---"
$maxRetries = 30
$retryCount = 0
$ready = $false
while ($retryCount -lt $maxRetries) {
    try {
        $result = & $py -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:$($preflight.selected_port)/ready', timeout=2)" -Timeout 10
        $ready = $true
        break
    } catch {
        $retryCount++
        Start-Sleep -Seconds 1
    }
}
if (-not $ready) {
    Write-Host "[WARN] Readiness probe did not complete after $maxRetries seconds. Service may still be starting up." -ForegroundColor Yellow
} else {
    Write-Host "Service ready after $retryCount retry(s)."
}

# --- Launch ---
Write-Host "Launching Gradio WebUI..."
& $py -m webui.app
