@echo off
REM Change this to your target directory
set SCRIPT_DIR=%~dp0

echo Starting UV Studio MQTT Broker...
echo.
echo IMPORTANT: For LAN access from your VM:
echo 1. In VirtualBox: VM Settings ^> Network ^> Advanced ^> Port Forwarding
echo 2. Add rule: Host Port 1883 -^> Guest Port 1883
echo 3. Other computers can then connect to your HOST PC's IP:1883
echo.

REM Use PowerShell to change into that directory and run uv with localhost
powershell -NoExit -Command "cd '%SCRIPT_DIR%'; echo 'Starting MQTT broker on localhost:1883...'; uv run main.py --start-broker"