@echo off
REM Change this to your target directory
set SCRIPT_DIR=%~dp0

REM Get the VM's IP address for bridged networking
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do set VM_IP=%%a
set VM_IP=%VM_IP: =%

echo Starting UV Studio MQTT Broker...
echo.
echo VM IP Address: %VM_IP%
echo MQTT Broker will be accessible at: %VM_IP%:1883
echo.
echo Network Mode: Bridged Adapter
echo Other computers can connect directly to: %VM_IP%:1883
echo.

REM Use PowerShell to change into that directory and run uv with 0.0.0.0 binding for bridged mode
powershell -NoExit -Command "cd '%SCRIPT_DIR%'; echo 'Starting MQTT broker...'; uv run main.py --start-broker --broker-host 0.0.0.0"