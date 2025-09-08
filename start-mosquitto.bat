@echo off
REM Mosquitto MQTT Broker Startup Script
set SCRIPT_DIR=%~dp0
set MOSQUITTO_PATH=C:\Program Files\mosquitto\mosquitto.exe

echo Starting Mosquitto MQTT Broker...
echo.

REM Check if Mosquitto is installed
if not exist "%MOSQUITTO_PATH%" (
    echo Error: Mosquitto not found at %MOSQUITTO_PATH%
    echo Please install Mosquitto from https://mosquitto.org/download/
    echo Or check if it's installed in a different location.
    pause
    exit /b 1
)

REM Create data directory if it doesn't exist
if not exist "%SCRIPT_DIR%mosquitto_data" mkdir "%SCRIPT_DIR%mosquitto_data"

REM Get local IP for display
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do set LOCAL_IP=%%a
set LOCAL_IP=%LOCAL_IP: =%

echo Mosquitto MQTT Broker Configuration:
echo - Executable: %MOSQUITTO_PATH%
echo - Port: 1883
echo - Bind: 0.0.0.0 (all interfaces)
echo - VM Access: localhost:1883
echo - LAN Access: %LOCAL_IP%:1883
echo - Anonymous connections: Enabled
echo.

REM Start Mosquitto with our configuration
echo Starting Mosquitto...
"%MOSQUITTO_PATH%" -c "%SCRIPT_DIR%mosquitto.conf" -v

pause
