# Automatic UV Studio

An automated software that interfaces with eufy Make Studio.

## Features

- **MQTT Interface**: Control print jobs via MQTT messages
- **Real-time Status**: Simple status ping every second for remote monitoring
- **12mm & 16mm Print Support**: Support for different canvas sizes
- **Retina/Non-Retina Image Support**: Automatic image scaling for UI detection

## MQTT Topics

### Command Topic: `uv_studio/command`
Send JSON commands to control the printer:

```json
{"command": "start_12mm_print"}
{"command": "start_16mm_print"}
{"command": "status"}
{"command": "stop"}
{"command": "clear_error"}
```

### Status Topic: `uv_studio/status`
Receive real-time status pings (every second):

```json
{
  "print_running": false
}
{
  "print_running": "12mm"
}
{
  "print_running": "16mm"
}
{
  "print_running": "stopping_12mm"
}
{
  "print_running": "stopping_16mm"
}
{
  "print_running": "error_12mm"
}
{
  "print_running": "error_16mm"
}
```
- `false`: Idle
- `12mm` / `16mm`: Print job running
- `stopping_12mm` / `stopping_16mm`: Stop signal received, stopping in progress
- `error_12mm` / `error_16mm`: Print job failed

### Physical Start Button Topic: `uv_studio/control`
A device should subscribe to this topic and when receiving the message   
```json
{"action": "press_start_button"}
```
it should press the physical start button of the eufy Make

## Installation

1. Install dependencies:
```bash
uv install
```

2. **Option A**: Use the embedded MQTT broker (recommended for testing):
```bash
# No additional setup needed - the embedded broker will start automatically
```

2. **Option B**: Use an external MQTT broker (e.g., Mosquitto):
```bash
# On macOS with Homebrew
brew install mosquitto
brew services start mosquitto

# On Ubuntu/Debian
sudo apt install mosquitto mosquitto-clients
sudo systemctl start mosquitto
```

## Usage

### Start the UV Studio MQTT Client

#### Basic usage (with embedded broker):
```bash
uv run main.py --start-broker
```

#### Advanced usage with custom settings:
```bash
# Custom broker settings
uv run main.py --broker-host 192.168.1.100 --broker-port 1884 --topic-prefix my_printer

# Start only the embedded broker (no UV Studio client)
uv run main.py --broker-only --broker-port 1884

# Connect to external broker
uv run main.py --broker-host mqtt.example.com --broker-port 8883
```

#### CLI Options:
- `--broker-host HOST` - MQTT broker host address (default: localhost)
- `--broker-port PORT` - MQTT broker port (default: 1883)
- `--topic-prefix PREFIX` - MQTT topic prefix (default: uv_studio)
- `--start-broker` - Start embedded MQTT broker before connecting
- `--broker-only` - Only start the MQTT broker (don't start UV Studio client)
- `--window-title TITLE` - Substring of the target app window title (default: eufy)
- `--retina` / `--no-retina` - Use retina or non-retina image mode

The client will:
- Connect to MQTT broker at specified host and port
- Subscribe to `{prefix}/command` for incoming commands
- Publish status pings to `{prefix}/status`

### Send Commands

#### Using the test client:
```bash
# Basic usage
python mqtt_test_client.py start_12mm_print

# With custom broker settings
python mqtt_test_client.py start_16mm_print --broker-host 192.168.1.100 --broker-port 1884

# Listen to status messages with custom settings
python mqtt_test_client.py listen --topic-prefix my_printer
```

#### Using mosquitto_pub:
```bash
# Start 12mm print (default settings)
mosquitto_pub -h localhost -t uv_studio/command -m '{"command": "start_12mm_print"}'

# With custom broker and topic
mosquitto_pub -h 192.168.1.100 -p 1884 -t my_printer/command -m '{"command": "start_16mm_print"}'
```

#### Monitor status pings:
```bash
# Default settings
mosquitto_sub -h localhost -t uv_studio/status

# Custom settings
mosquitto_sub -h 192.168.1.100 -p 1884 -t my_printer/status
```

## Configuration

The system supports flexible configuration via command-line arguments:

### MQTT Settings
- **Broker Host**: `--broker-host` (default: localhost)
- **Broker Port**: `--broker-port` (default: 1883)  
- **Topic Prefix**: `--topic-prefix` (default: uv_studio)

### Embedded Broker
- **Start Broker**: `--start-broker` - Start embedded MQTT broker
- **Broker Only**: `--broker-only` - Only run the broker (no UV Studio client)

### Image Mode
- **Retina**: `--retina` (default: True)
- **Non-Retina**: `--no-retina`

### Examples
```bash
# Custom broker settings
uv run main.py --broker-host 192.168.1.100 --broker-port 1884 --topic-prefix factory_printer

# Development setup with embedded broker
uv run main.py --start-broker --broker-port 1885

# Production setup
uv run main.py --broker-host mqtt.production.com --broker-port 8883 --topic-prefix prod_uv_studio
```

## Workflow

The print workflow includes:

1. **Window Preparation**: Activate eufy Make Studio window
2. **UI Reset**: Reset the user interface
3. **Online Check**: Verify printer is online
4. **Idle Check**: Ensure printer is not busy
5. **Tray Scan**: Scan the print tray
6. **Print Start**: Begin the print job

Each step is logged to both console and MQTT status topic.

## Status Ping System

- Every second, a status ping is published to MQTT with the current print state:
    - `false`: Idle
    - `12mm` / `16mm`: Print job running
    - `stopping_12mm` / `stopping_16mm`: Stop signal received, stopping in progress
    - `error_12mm` / `error_16mm`: Print job failed
- The state returns to `false` when idle or after stop/error is cleared.

## Error Handling

- **Concurrent Jobs**: Only one print job can run at a time
- **Connection Issues**: MQTT connection failures are logged
- **Print Failures**: All workflow errors are reported via status ping
- **Stop Signal**: Stopping state is reported until stop is complete

## Thread Safety

The system uses threading locks to ensure:
- Only one print job runs at a time
- Thread-safe MQTT publishing
- Proper cleanup on job completion
