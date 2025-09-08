@echo off
REM Change this to your target directory
set TARGET_DIR=C:\path\to\your\project

REM Use PowerShell to navigate and run the command
powershell -NoExit -Command "cd '%TARGET_DIR%'; uv run main.py --start-broker"