<#
.SYNOPSIS
  Start an interactive Codex session in codex_sandbox/ with the SimForge MCP server attached.
.DESCRIPTION
  Uses your existing Codex sign-in (run `codex login` once). Codex may write only inside
  codex_sandbox/ and can validate, test and submit drafts for administrator approval.
.EXAMPLE
  .\scripts\codex-sandbox.ps1
  .\scripts\codex-sandbox.ps1 -Prompt "Create a Minecraft-style mining village crisis"
#>
param([string]$Prompt = "", [switch]$DryRun)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Server = Join-Path $Root "scripts\mcp_simforge.py"
$Workspace = Join-Path $Root "codex_sandbox"
if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
  Write-Error "Codex CLI not found. Install it with: npm install -g @openai/codex ; then run: codex login"
}
# A half-deleted .venv still has python.exe, so check that it can load the MCP server's dependencies.
$venvOk = $false
if (Test-Path $Python) {
  $ErrorActionPreference = "Continue"
  try { & $Python -c "import mcp, yaml, networkx" 2>$null; $venvOk = ($LASTEXITCODE -eq 0) } catch { $venvOk = $false }
  $ErrorActionPreference = "Stop"
}
if (-not $venvOk) { Write-Error "The project environment (.venv) is missing or broken. Run $Root\setup.cmd first." }
# codex prints its status on stderr; run through cmd so PowerShell does not treat it as an error.
$status = (cmd /c "codex login status 2>&1") -join " "
if ($status -notmatch "Logged in") {
  Write-Host "Codex is not signed in. Opening codex login..." -ForegroundColor Yellow
  & codex login
}
New-Item -ItemType Directory -Force (Join-Path $Workspace "drafts") | Out-Null
# TOML single-quoted strings are literal, so Windows paths need no escaping.
$DataDir = Join-Path $Root "data"
$CodexArgs = @(
  "-C", $Workspace,
  "--sandbox", "workspace-write",
  "-c", "mcp_servers.simforge.command='$Python'",
  "-c", "mcp_servers.simforge.args=['$Server']",
  "-c", "mcp_servers.simforge.env={SIMFORGE_DATA_DIR='$DataDir'}"
)
if ($Prompt) { $CodexArgs += $Prompt }
if ($DryRun) { Write-Output ("codex " + ($CodexArgs -join " ")); return }
Write-Host "Starting Codex in $Workspace with the SimForge MCP server..." -ForegroundColor Cyan
& codex @CodexArgs
