@echo off
REM Double-click launcher: starts the dashboard in the project's venv.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1"
if errorlevel 1 pause
