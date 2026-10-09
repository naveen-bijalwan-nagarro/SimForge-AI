@echo off
rem Double-click or run from any folder: stops every SimForge API server and Vite dev server (localhost:5173)
rem started from this project. Add -List to only show what is running.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop.ps1" %*
rem Keep the window open when double-clicked so the result can be read.
echo %cmdcmdline% | find /i "%~0" >nul && pause
