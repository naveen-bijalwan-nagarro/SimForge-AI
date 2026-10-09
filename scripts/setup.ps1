<#
.SYNOPSIS
  One-time setup: Python environment (.venv), pinned dependencies and the React build.
.DESCRIPTION
  Safe to re-run and works from any directory. A working Python 3.12+ .venv is reused;
  a broken one (for example half-deleted, or missing pyvenv.cfg) or one made with an older
  Python is rebuilt automatically. -Recreate forces a clean rebuild.
.EXAMPLE
  .\scripts\setup.ps1
  .\scripts\setup.ps1 -Python C:\Python312\python.exe
  .\scripts\setup.ps1 -Recreate
#>
param([string]$Python = "", [switch]$Recreate)
$ErrorActionPreference = "Stop"
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$venvDir = Join-Path $taskRoot '.venv'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'

# True when $exe starts and is Python 3.12+. A broken venv ("No pyvenv.cfg file") counts as unusable.
function Test-Python312([string]$exe) {
    $ErrorActionPreference = 'Continue'
    try {
        $out = & $exe -c "import sys; print(sys.version_info >= (3, 12))" 2>$null
        return ($LASTEXITCODE -eq 0 -and "$out".Trim() -eq 'True')
    } catch { return $false }
}

function Test-Pip([string]$exe) {
    $ErrorActionPreference = 'Continue'
    & $exe -c "import pip" 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Get-VenvProcesses {
    Get-Process python*, pythonw* -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path.StartsWith($venvDir, [StringComparison]::OrdinalIgnoreCase) }
}

if (Test-Path -LiteralPath $venvDir) {
    $reason = $null
    if ($Recreate) { $reason = 'Recreating .venv as requested' }
    elseif (-not (Test-Python312 $venvPython)) { $reason = '.venv exists but is not a working Python 3.12+ environment; rebuilding it' }
    if ($reason) {
        Write-Host $reason -ForegroundColor Yellow
        $busy = @(Get-VenvProcesses)
        if ($busy.Count) {
            $ids = ($busy | ForEach-Object { $_.Id }) -join ', '
            throw "SimForge is still running from .venv (process id $ids). Stop it with Ctrl+C in its window or: Stop-Process -Id $ids ; then run setup again."
        }
        try { Remove-Item -LiteralPath $venvDir -Recurse -Force }
        catch { throw "Could not delete .venv ($($_.Exception.Message)). Close editors or terminals using it and run setup again." }
    } else {
        Write-Host 'Reusing the existing .venv' -ForegroundColor Green
    }
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    if ($Python -and -not (Test-Python312 $Python)) { throw "$Python is not a working Python 3.12+ interpreter" }
    $taskCandidates = @()
    if ($Python) { $taskCandidates += $Python }
    $taskCandidates += @(
        'python', 'python3',
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
    )
    $taskInterpreter = $null
    foreach ($taskCandidate in $taskCandidates) {
        if ((Get-Command $taskCandidate -ErrorAction SilentlyContinue) -and (Test-Python312 $taskCandidate)) {
            $taskInterpreter = $taskCandidate; break
        }
    }
    if (-not $taskInterpreter) { throw 'Python 3.12+ is required. Install it from python.org, or run: .\scripts\setup.ps1 -Python C:\path\to\python.exe' }
    Write-Host "Creating .venv with $taskInterpreter"
    & $taskInterpreter -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment' }
}

# A .venv made by other tools (for example uv) may have no pip.
if (-not (Test-Pip $venvPython)) { & $venvPython -m ensurepip --upgrade }
& $venvPython -m pip install -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed' }

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Node.js 22+ with npm is required for the React build: https://nodejs.org' }
Push-Location frontend
try {
    & npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'npm install failed' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'React build failed' }
} finally { Pop-Location }
Write-Host "Ready. Start SimForge with: $taskRoot\start.cmd  (or .\scripts\start.ps1 from the project folder), then open http://127.0.0.1:8000" -ForegroundColor Green
