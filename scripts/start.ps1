<#
.SYNOPSIS
  Start SimForge AI: the React UI and the API together. Works from any directory.
.DESCRIPTION
  Default: one server on http://127.0.0.1:<Port> serves the built React UI (frontend/dist) and the
  API. The UI is rebuilt first when it is missing or older than frontend/src, so UI changes always show.
  -Dev: API with auto-reload on <Port> plus the Vite dev server with hot reload on http://127.0.0.1:5173.
  -Open: open the browser once the app answers. Ctrl+C stops everything.
.EXAMPLE
  .\scripts\start.ps1
  .\scripts\start.ps1 -Open -Port 8018
  .\scripts\start.ps1 -Dev -Open
#>
param([int]$Port = 8000, [switch]$Reload, [switch]$Dev, [switch]$Open, [int]$UiPort = 5173)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$venvPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
$frontend = Join-Path $taskRoot 'frontend'
$setupHint = "Run setup first: $taskRoot\setup.cmd  (or .\scripts\setup.ps1 from the project folder)"

# A half-deleted or wrong-version .venv still has python.exe, so check that it actually runs the app.
$healthy = $false
if (Test-Path -LiteralPath $venvPython) {
    $ErrorActionPreference = 'Continue'
    try {
        & $venvPython -c "import sys, fastapi, uvicorn, simpy; sys.exit(0 if sys.version_info >= (3, 12) else 1)" 2>$null
        $healthy = ($LASTEXITCODE -eq 0)
    } catch { $healthy = $false }
    $ErrorActionPreference = 'Stop'
}
if (-not $healthy) { throw "The Python environment (.venv) is missing, broken or incomplete. $setupHint" }

function Assert-PortFree([int]$p, [string]$flag) {
    $busy = Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($busy) { throw "Port $p is already in use (process id $($busy.OwningProcess)). Stop that process or choose another port: .\scripts\start.ps1 $flag" }
}
Assert-PortFree $Port '-Port 8018'
if ($Dev) { Assert-PortFree $UiPort '-Dev -UiPort 5174' }

$hasNpm = [bool](Get-Command npm.cmd -ErrorAction SilentlyContinue)
function Install-Frontend {
    if (Test-Path -LiteralPath (Join-Path $frontend 'node_modules\vite')) { return }
    if (-not $hasNpm) { throw 'Node.js 22+ with npm is required for the React UI: https://nodejs.org' }
    Write-Host 'Installing UI packages (npm ci)...' -ForegroundColor Cyan
    Push-Location $frontend
    try { & npm.cmd ci; if ($LASTEXITCODE -ne 0) { throw 'npm install failed' } } finally { Pop-Location }
}

if (-not $Dev) {
    # Rebuild when the UI build is missing or any UI source is newer than it.
    $built = Join-Path $frontend 'dist\index.html'
    $stale = -not (Test-Path -LiteralPath $built)
    if (-not $stale) {
        $builtAt = (Get-Item -LiteralPath $built).LastWriteTimeUtc
        $sources = @(Get-ChildItem -LiteralPath (Join-Path $frontend 'src') -Recurse -File) +
            @(Get-Item -LiteralPath (Join-Path $frontend 'index.html'), (Join-Path $frontend 'vite.config.js'), (Join-Path $frontend 'package-lock.json') -ErrorAction SilentlyContinue)
        $stale = [bool]($sources | Where-Object { $_.LastWriteTimeUtc -gt $builtAt } | Select-Object -First 1)
    }
    if ($stale -and -not $hasNpm) {
        if (Test-Path -LiteralPath $built) { Write-Warning 'UI sources changed but npm is not installed; serving the previous UI build.' }
        else { throw "The React UI has not been built and npm is not installed (Node.js 22+: https://nodejs.org). $setupHint" }
    } elseif ($stale) {
        Install-Frontend
        Write-Host 'Building the React UI (it changed since the last build)...' -ForegroundColor Cyan
        Push-Location $frontend
        try { & npm.cmd run build; if ($LASTEXITCODE -ne 0) { throw 'React build failed' } } finally { Pop-Location }
    }
}

# Only local development auto-enables Codex; production always requires explicit opt-in.
if ($env:SIMFORGE_ENV -ne 'production' -and -not $env:SIMFORGE_CODEX_ENABLED -and (Get-Command codex -ErrorAction SilentlyContinue)) { $env:SIMFORGE_CODEX_ENABLED = '1' }
$taskArgs = @('-m','uvicorn','backend.main:app','--host','127.0.0.1','--port',"$Port")
if ($Reload -or $Dev) { $taskArgs += @('--reload', '--reload-dir', 'backend') }

$uiUrl = if ($Dev) { "http://127.0.0.1:$UiPort" } else { "http://127.0.0.1:$Port" }
$vite = $null
$opener = $null
try {
    if ($Dev) {
        if (-not (Get-Command node.exe -ErrorAction SilentlyContinue)) { throw 'Node.js 22+ is required for -Dev: https://nodejs.org' }
        Install-Frontend
        # Vite proxies /api to this API port (see frontend/vite.config.js).
        $env:SIMFORGE_API_URL = "http://127.0.0.1:$Port"
        $vite = Start-Process -FilePath 'node.exe' -WorkingDirectory $frontend -WindowStyle Hidden -PassThru `
            -ArgumentList "`"$(Join-Path $frontend 'node_modules\vite\bin\vite.js')`"", '--host', '127.0.0.1', '--port', "$UiPort", '--strictPort'
    }
    if ($Open) {
        $opener = Start-Job -ArgumentList $uiUrl, $Port -ScriptBlock {
            param($url, $apiPort)
            for ($i = 0; $i -lt 120; $i++) {
                if (Get-NetTCPConnection -State Listen -LocalPort $apiPort -ErrorAction SilentlyContinue) {
                    try { Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 2 | Out-Null; Start-Process $url; return } catch { }
                }
                Start-Sleep -Milliseconds 500
            }
        }
    }
    Write-Host ''
    if ($Dev) {
        Write-Host "  SimForge AI (development): UI with hot reload $uiUrl   API http://127.0.0.1:$Port/docs" -ForegroundColor Green
    } else {
        Write-Host "  SimForge AI: $uiUrl   (UI and API on one server; API docs at /docs)" -ForegroundColor Green
    }
    Write-Host '  Sign in as admin/admin123 (Admin / Trainer) or learner/learner123. Ctrl+C stops it.' -ForegroundColor Green
    Write-Host ''
    & $venvPython @taskArgs
} finally {
    $ErrorActionPreference = 'Continue'
    if ($vite -and -not $vite.HasExited) { & taskkill.exe /PID $vite.Id /T /F 2>&1 | Out-Null }
    if ($opener) { Remove-Job $opener -Force -ErrorAction SilentlyContinue }
}
