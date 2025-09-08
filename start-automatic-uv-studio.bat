@echo off
REM Change this to your target directory
set SCRIPT_DIR=%~dp0

REM Use PowerShell to change into that directory and run uv
powershell -NoExit -Command "cd '%SCRIPT_DIR%'; uv run main.py --start-broker"