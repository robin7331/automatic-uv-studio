@echo off
REM Combined startup script - starts both Mosquitto and UV Studio
set SCRIPT_DIR=%~dp0
set MOSQUITTO_PATH=C:\Program Files\mosquitto\mosquitto.exe

echo UV Studio with Mosquitto MQTT Broker
echo ====================================
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

echo Network Configuration:
echo - Executable: %MOSQUITTO_PATH%
echo - VM Internal: localhost:1883
echo - LAN Access: %LOCAL_IP%:1883
echo - Topics: uv_studio/command, uv_studio/status, uv_studio/control
echo.

REM Check if Mosquitto is already running
echo Checking if Mosquitto is already running...
tasklist /fi "imagename eq mosquitto.exe" 2>nul | find /i "mosquitto.exe" >nul
if %errorlevel% equ 0 (
    echo Mosquitto is already running - skipping startup
) else (
    echo Starting Mosquitto MQTT Broker...
    start "Mosquitto MQTT Broker" /min "%MOSQUITTO_PATH%" -c "%SCRIPT_DIR%mosquitto.conf" -v
    echo Waiting for broker to start...
    timeout /t 3 /nobreak >nul
)

echo Starting UV Studio MQTT Client...
powershell -NoExit -Command "cd '%SCRIPT_DIR%'; echo 'UV Studio starting...'; uv run main.py --broker-host localhost --broker-port 1883"
