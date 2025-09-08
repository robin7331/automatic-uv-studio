@echo off
REM Change this to your target directory
set SCRIPT_DIR=%~dp0

REM Get the local IP address
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do set IP=%%a
set IP=%IP: =%

echo Starting UV Studio MQTT Broker...
echo VM IP Address: %IP%
echo MQTT Broker will be accessible at: %IP%:1883
echo.

REM Use PowerShell to change into that directory and run uv with 0.0.0.0 binding
powershell -NoExit -Command "cd '%SCRIPT_DIR%'; echo 'MQTT Broker accessible on LAN at: %IP%:1883'; uv run main.py --start-broker --broker-host 0.0.0.0"