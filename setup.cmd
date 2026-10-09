@echo off
rem Double-click or run from any folder: creates/repairs .venv, installs dependencies and builds React.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1" %*
pause
