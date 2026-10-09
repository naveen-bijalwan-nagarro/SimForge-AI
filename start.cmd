@echo off
rem Double-click or run from any folder: builds the UI if needed, starts SimForge AI (UI + API) and opens the browser.
rem Arguments pass through, e.g. start.cmd -Port 8018   or   start.cmd -Dev  (hot-reload UI on 5173).
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" -Open %*
if errorlevel 1 pause
