<#
.SYNOPSIS
  Stop SimForge AI completely. Works from any directory.
.DESCRIPTION
  Stops every SimForge API server run from this project (uvicorn, including --reload workers and the
  Codex jobs it started), leftover reload workers whose server already died, orphaned Codex jobs, and
  every Vite dev server for this project (http://localhost:5173). Interactive Codex sandbox sessions
  are left alone. Safe to run when nothing is running.
.EXAMPLE
  .\scripts\stop.ps1          # stop everything
  .\scripts\stop.ps1 -List    # only show what would be stopped
#>
param([switch]$List, [int[]]$UiPorts = @(5173, 5174, 5175, 5176))
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $root '.venv'
$frontend = Join-Path $root 'frontend'

# .venv\Scripts\python.exe is a launcher that starts the base interpreter. Reload workers, and a
# server whose launcher was already killed, run on that base interpreter, so recognise it too.
$base = $null
$cfg = Join-Path $venv 'pyvenv.cfg'
if (Test-Path -LiteralPath $cfg) {
    $settings = @{}
    foreach ($line in Get-Content -LiteralPath $cfg) {
        if ($line -match '^\s*([\w-]+)\s*=\s*(.+?)\s*$') { $settings[$Matches[1]] = $Matches[2] }
    }
    if ($settings['executable']) { $base = $settings['executable'] }
    elseif ($settings['home']) { $base = Join-Path $settings['home'] 'python.exe' }
}

function Test-Contains([string]$text, [string]$part) {
    $text -and $text.Replace('/', '\').IndexOf($part, [StringComparison]::OrdinalIgnoreCase) -ge 0
}

function Find-SimForge {
    $all = @(Get-CimInstance Win32_Process)
    $alive = @{}
    foreach ($p in $all) { $alive[[int]$p.ProcessId] = $true }
    $ports = @{}
    foreach ($c in @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue)) {
        $key = [int]$c.OwningProcess
        if (-not $ports.ContainsKey($key)) { $ports[$key] = New-Object System.Collections.Generic.List[int] }
        if (-not $ports[$key].Contains([int]$c.LocalPort)) { $ports[$key].Add([int]$c.LocalPort) }
    }
    $found = @()
    foreach ($p in $all) {
        $cmd = [string]$p.CommandLine
        $exe = [string]$p.ExecutablePath
        $parentGone = -not $alive.ContainsKey([int]$p.ParentProcessId)
        $isBase = $base -and $exe -and ($exe -ieq $base)
        $what = $null
        if ($p.Name -like 'python*') {
            if ($cmd -match 'uvicorn\s+backend\.main:app' -and ((Test-Contains $exe $venv) -or ($isBase -and $parentGone))) {
                $what = 'API server'
            } elseif ($isBase -and $parentGone -and $cmd -match 'multiprocessing') {
                $what = 'leftover API reload worker'
            }
        } elseif ($p.Name -like 'node*' -and $cmd -match 'vite') {
            # A full path to vite.js names its project: only ours counts. A relative path (older
            # start.ps1 -Dev runs) is recognised by listening on a SimForge UI port.
            $absolute = [regex]::Match($cmd, '[A-Za-z]:[\\/][^"]*?vite[\\/]bin[\\/]vite\.js')
            $onUiPort = $ports.ContainsKey([int]$p.ProcessId) -and @($ports[[int]$p.ProcessId] | Where-Object { $UiPorts -contains $_ }).Count
            if ((Test-Contains $cmd $frontend) -or (-not $absolute.Success -and $onUiPort)) { $what = 'Vite dev server' }
        } elseif ($p.Name -like 'codex*' -and $cmd -match '\sexec\s' -and $parentGone -and (Test-Contains $cmd $root)) {
            $what = 'orphaned Codex job'
        }
        if ($what) {
            $found += [pscustomobject]@{
                Id       = [int]$p.ProcessId
                Parent   = [int]$p.ParentProcessId
                What     = $what
                Ports    = if ($ports.ContainsKey([int]$p.ProcessId)) { ($ports[[int]$p.ProcessId] | Sort-Object) -join ', ' } else { '' }
                Command  = if ($cmd.Length -gt 110) { $cmd.Substring(0, 110) + '...' } else { $cmd }
            }
        }
    }
    # A process started by another match is stopped with its parent's process tree.
    $ids = @($found | ForEach-Object { $_.Id })
    @($found | Where-Object { $ids -notcontains $_.Parent })
}

$targets = @(Find-SimForge)
if (-not $targets.Count) {
    Write-Host 'No SimForge servers are running.' -ForegroundColor Green
    return
}
Write-Host ($(if ($List) { 'Running SimForge processes:' } else { 'Stopping:' })) -ForegroundColor Cyan
$targets | Format-Table Id, What, Ports, Command -AutoSize -Wrap | Out-String -Width 220 | Write-Host
if ($List) { return }

$ErrorActionPreference = 'Continue'
foreach ($t in $targets) {
    # /T also stops everything the process started (reload workers, esbuild, Codex jobs); /F is required
    # for console programs. SQLite's write-ahead log keeps the database consistent.
    & taskkill.exe /PID $t.Id /T /F *> $null
}
Start-Sleep -Milliseconds 800
$left = @(Find-SimForge)
if ($left.Count) {
    Write-Warning ("Still running: " + (($left | ForEach-Object { "$($_.What) (process id $($_.Id))" }) -join '; ') + '. Run this again as the user that started them.')
    exit 1
}
Write-Host "SimForge stopped: $($targets.Count) process tree(s)." -ForegroundColor Green
