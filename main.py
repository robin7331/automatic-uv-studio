import pyautogui
import pywinctl as pwc
from workflows.reset_ui import ResetUIWorkflow
from workflows.check_if_online import CheckIfOnline
from workflows.check_if_printer_idle import CheckIfIdle
from workflows.scan_tray import ScanTray
from workflows.workflow import Workflow
from workflows.start_print import StartPrint
from workflows.stop import Stop
from workflows.check_if_low_ink import CheckIfLowInk
from workflows.check_if_should_moisturize import CheckIfShouldMoisturize
from workflows.select_zero_point_alignment import SelectZeroPointAlignment
import pyscreeze
import threading
import logging
import sys
import json
import time
import argparse
import asyncio
from amqtt.client import MQTTClient
from amqtt.mqtt.constants import QOS_1

pyscreeze.USE_IMAGE_NOT_FOUND_EXCEPTION = False

# Default MQTT Configuration
DEFAULT_MQTT_BROKER = "localhost"
DEFAULT_MQTT_PORT = 1883
DEFAULT_TOPIC_PREFIX = "uv_studio"

# Global variables
print_lock = threading.Lock()
current_print_thread = None
stop_print_event = threading.Event()
mqtt_client = None
low_ink = False
mqtt_loop = None


class Config:
    """Configuration class to hold MQTT settings"""

    def __init__(
        self,
        broker_host=DEFAULT_MQTT_BROKER,
        broker_port=DEFAULT_MQTT_PORT,
        topic_prefix=DEFAULT_TOPIC_PREFIX,
    ):
        self.mqtt_broker = broker_host
        self.mqtt_port = broker_port
        self.topic_prefix = topic_prefix
        self.topic_command = f"{topic_prefix}/command"
        self.topic_status = f"{topic_prefix}/status"
        self.topic_control = f"{topic_prefix}/control"


# Global config instance
config = Config()


# Configure logging
def setup_logging():
    """Setup logging with console handler"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger(__name__)


# Initialize logger
logger = setup_logging()


def prepare_window():
    # activate the window and raise an error if not found
    windows = pwc.getWindowsWithTitle("eufy", pwc.Re.CONTAINS)
    # If no window is found, return False (caller handles error/reporting)
    if not windows:
        return False

    window = windows[0]
    window.activate(wait=True)

    # get the window size and position
    return window.rect


def stop_print():
    window_rect = prepare_window()

    prepare_msg = f"Stopping"
    print(prepare_msg)
    logger.info(prepare_msg)
    publish_status_message(prepare_msg, "info")

    if not window_rect:
        error_msg = f"Could not prepare window"
        print(error_msg)
        logger.error(error_msg)
        publish_status_message(error_msg, "error")
        return False

    # reset the screen
    stop = Stop(window_rect=window_rect)
    if not stop.run():
        error_msg = f"Could not stop"
        print(error_msg)
        logger.error(error_msg)
        publish_status_message(error_msg, "error")
        return False


def start_print(canvas_index=0):
    global stop_print_event

    window_rect = prepare_window()

    if not window_rect:
        error_msg = f"Could not prepare window"
        print(error_msg)
        logger.error(error_msg)
        publish_status_message(error_msg, "error")
        return False

    prefix = "[12mm] " if canvas_index == 0 else "[16mm] "

    prepare_msg = f"{prefix}Preparing eufy Make Studio"
    print(prepare_msg)
    logger.info(prepare_msg)
    publish_status_message(prepare_msg, "info")

    # Check for stop signal
    if stop_print_event.is_set():
        logger.info(f"{prefix}Print stopped during preparation")
        return False

    if not window_rect:
        error_msg = f"{prefix}Could not prepare window"
        print(error_msg)
        logger.error(error_msg)
        publish_status_message(error_msg, "error")
        return False

    # reset the screen
    reset_ui = ResetUIWorkflow(window_rect=window_rect)
    if not reset_ui.run():
        error_msg = f"{prefix}Could not reset the UI"
        print(error_msg)
        logger.error(error_msg)
        publish_status_message(error_msg, "error")
        return False

    # Check for stop signal
    if stop_print_event.is_set():
        logger.info(f"{prefix}Print stopped during UI reset")
        return False

    # check if printer online
    check_if_online = CheckIfOnline(window_rect=window_rect)
    if not check_if_online.run():
        error_msg = f"{prefix}Printer not online"
        print(error_msg)
        logger.error(error_msg)
        publish_status_message(error_msg, "error")
        return False

    # Check for stop signal
    if stop_print_event.is_set():
        logger.info(f"{prefix}Print stopped during online check")
        return False

    # Make sure the printer is idle
    check_if_idle = CheckIfIdle(window_rect=window_rect)
    if not check_if_idle.run():
        error_msg = f"{prefix}Printer not idle"
        print(error_msg)
        logger.error(error_msg)
        publish_status_message(error_msg, "error")
        return False

    # Check for stop signal
    if stop_print_event.is_set():
        logger.info(f"{prefix}Print stopped during idle check")
        return False

    # Scan the tray
    scan_msg = f"{prefix}Scanning the tray"
    print(scan_msg)
    logger.info(scan_msg)
    publish_status_message(scan_msg, "info")
    scan_tray = ScanTray(window_rect=window_rect)
    if not scan_tray.run(canvas_index=canvas_index):
        error_msg = f"{prefix}Failed to scan tray"
        print(error_msg)
        logger.error(error_msg)
        publish_status_message(error_msg, "error")
        return False

    # Check for stop signal
    if stop_print_event.is_set():
        logger.info(f"{prefix}Print stopped during tray scan")
        return False

    # Print
    loggableName = "12mm" if canvas_index == 0 else "16mm"
    start_msg = f"{prefix}Starting {loggableName} print"
    print(start_msg)
    logger.info(start_msg)
    publish_status_message(start_msg, "info")
    start_print_workflow = StartPrint(
        window_rect=window_rect, publish_control_message=publish_control_message
    )
    if not start_print_workflow.run(canvas_index=canvas_index):
        error_msg = f"{prefix}Failed to print"
        print(error_msg)
        logger.error(error_msg)
        publish_status_message(error_msg, "error")
        return False

    # Check for stop signal
    if stop_print_event.is_set():
        logger.info(f"{prefix}Print stopped during print execution")
        return False

    success_msg = f"{prefix}Print completed successfully"
    print(success_msg)
    logger.info(success_msg)
    publish_status_message(success_msg, "info")
    return True


def start_print_async(canvas_index, print_type):
    """Run the print workflow asynchronously"""
    global current_print_thread, stop_print_event

    # Check if we can acquire the lock (non-blocking)
    if not print_lock.acquire(blocking=False):
        error_msg = (
            f"Cannot start {print_type} print - another print job is already running"
        )
        logger.warning(error_msg)
        print(error_msg)
        publish_status_message(error_msg, "warning")
        return False

    try:
        # Clear any previous stop signal
        stop_print_event.clear()

        current_print_thread = threading.current_thread()
        start_msg = f"Starting {print_type} print (canvas_index={canvas_index})"
        logger.info(start_msg)
        print(start_msg)
        publish_status_message(start_msg, "info")

        # Check for stop signal before starting
        if stop_print_event.is_set():
            logger.info(f"{print_type} print was stopped before starting")
            publish_status_message(
                f"{print_type} print was stopped before starting", "info"
            )
            return False

        success = start_print(canvas_index=canvas_index)

        # Check for stop signal after print attempt
        if stop_print_event.is_set():
            logger.info(f"{print_type} print was stopped")
            publish_status_message(f"{print_type} print was stopped", "info")
            stop_print()  # Call the stop_print function to handle cleanup
            return False

        if success:
            success_msg = f"Completed {print_type} print successfully"
            logger.info(success_msg)
            print(success_msg)
            publish_status_message(success_msg, "info")
        else:
            error_msg = f"Failed to complete {print_type} print"
            logger.error(error_msg)
            print(error_msg)
            publish_status_message(error_msg, "error")

        return success
    except Exception as e:
        error_msg = f"Error during {print_type} print: {str(e)}"
        logger.error(error_msg)
        print(error_msg)
        publish_status_message(error_msg, "error")
        return False
    finally:
        current_print_thread = None
        print_lock.release()
        finish_msg = f"{print_type} print thread finished"
        logger.info(finish_msg)
        print(finish_msg)
        publish_status_message(finish_msg, "info")


def publish_status_message(message, level="info"):
    """Publish a status message to MQTT"""
    global mqtt_loop

    if mqtt_loop and not mqtt_loop.is_closed():
        status_message = {
            "timestamp": time.time(),
            "level": level,
            "message": message,
            "print_job_running": current_print_thread
            and current_print_thread.is_alive(),
        }

        # Schedule the async publish on the event loop
        try:
            asyncio.run_coroutine_threadsafe(
                _publish_status_async(status_message), mqtt_loop
            )
        except Exception as e:
            logger.error(f"Failed to schedule status message: {str(e)}")
    else:
        logger.warning("MQTT client not connected, cannot publish status message")


async def _publish_status_async(status_message):
    """Async helper to publish status message"""
    global mqtt_client

    if mqtt_client:
        try:
            await mqtt_client.publish(
                config.topic_status, json.dumps(status_message).encode(), qos=QOS_1
            )
            logger.debug(f"Published status: {status_message['message']}")
        except Exception as e:
            logger.error(f"Failed to publish MQTT status message: {str(e)}")


def publish_control_message(action):
    """Publish a control message to MQTT"""
    global mqtt_loop

    if mqtt_loop and not mqtt_loop.is_closed():
        control_message = {"action": action, "timestamp": time.time()}

        # Schedule the async publish on the event loop
        try:
            asyncio.run_coroutine_threadsafe(
                _publish_control_async(control_message), mqtt_loop
            )
        except Exception as e:
            logger.error(f"Failed to schedule control message: {str(e)}")
    else:
        logger.warning("MQTT client not connected, cannot publish control message")


async def _publish_control_async(control_message):
    """Async helper to publish control message"""
    global mqtt_client

    if mqtt_client:
        try:
            await mqtt_client.publish(
                config.topic_control, json.dumps(control_message).encode(), qos=QOS_1
            )
            logger.info(f"Published control message: {control_message['action']}")
        except Exception as e:
            logger.error(f"Failed to publish control message: {str(e)}")


def handle_start_print_command(print_type, canvas_index):
    """Handle start print command from MQTT"""
    # Check if another print is already running
    if current_print_thread and current_print_thread.is_alive():
        error_msg = (
            f"Cannot start {print_type} print - another print job is already running"
        )
        logger.warning(error_msg)
        publish_status_message(error_msg, "warning")
        return

    # Start the print job in a separate thread
    thread = threading.Thread(
        target=start_print_async, args=(canvas_index, print_type), daemon=True
    )
    thread.start()

    success_msg = f"{print_type} print job started"
    logger.info(success_msg)
    publish_status_message(success_msg, "info")


def handle_status_command():
    """Handle status request command from MQTT"""
    is_running = current_print_thread and current_print_thread.is_alive()
    status_msg = f"Print job running: {is_running}"
    logger.info(status_msg)
    publish_status_message(status_msg, "info")


def handle_stop_command():
    """Handle stop command from MQTT"""
    global stop_print_event

    if current_print_thread and current_print_thread.is_alive():
        # Signal the print thread to stop
        stop_print_event.set()

        # Call stop_print to handle any immediate UI cleanup
        stop_print()

        logger.info("Print job stop signal sent")
        publish_status_message("Print job stop signal sent", "info")
    else:
        logger.warning("No print job is currently running")
        publish_status_message("No print job is currently running", "warning")


# MQTT async functions for aMQTT
async def handle_mqtt_message(topic, payload):
    """Handle incoming MQTT messages"""
    try:
        payload_str = payload.decode()
        logger.info(f"Received MQTT message on topic {topic}: {payload_str}")

        payload_json = json.loads(payload_str)

        if topic == config.topic_command:
            command = payload_json.get("command")

            if command == "start_12mm_print":
                handle_start_print_command("12mm", 0)
            elif command == "start_16mm_print":
                handle_start_print_command("16mm", 1)
            elif command == "status":
                handle_status_command()
            elif command == "stop":
                handle_stop_command()
            else:
                logger.warning(f"Unknown command: {command}")
                publish_status_message(f"Unknown command: {command}", "warning")

    except json.JSONDecodeError:
        logger.error("Failed to decode JSON message")
        publish_status_message("Failed to decode JSON message", "error")
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        publish_status_message(f"Error processing message: {str(e)}", "error")


async def mqtt_message_handler():
    """Async message handler for aMQTT"""
    global mqtt_client

    try:
        while True:
            message = await mqtt_client.deliver_message()
            packet = message.publish_packet
            topic = packet.variable_header.topic_name
            payload = packet.payload.data

            # Handle message in background to avoid blocking
            asyncio.create_task(handle_mqtt_message(topic, payload))

    except Exception as e:
        logger.error(f"Error in MQTT message handler: {str(e)}")


async def setup_mqtt_async():
    """Setup aMQTT client and connect to broker"""
    global mqtt_client

    try:
        mqtt_client = MQTTClient()

        broker_url = f"mqtt://{config.mqtt_broker}:{config.mqtt_port}"
        logger.info(f"Connecting to MQTT broker at {broker_url}")

        await mqtt_client.connect(broker_url)
        logger.info("Connected to MQTT broker")

        # Subscribe to command topic
        await mqtt_client.subscribe([(config.topic_command, QOS_1)])
        logger.info(f"Subscribed to {config.topic_command}")

        # Send initial status
        await _publish_status_async(
            {
                "timestamp": time.time(),
                "level": "info",
                "message": "UV Studio connected to MQTT broker",
                "print_job_running": False,
            }
        )

        # Start message handler
        asyncio.create_task(mqtt_message_handler())

        return True

    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {str(e)}")
        return False


def setup_mqtt():
    """Setup MQTT client and start async loop"""
    global mqtt_loop

    # Create new event loop for MQTT
    mqtt_loop = asyncio.new_event_loop()

    def run_mqtt_loop():
        asyncio.set_event_loop(mqtt_loop)
        try:
            mqtt_loop.run_until_complete(setup_mqtt_async())
            mqtt_loop.run_forever()
        except Exception as e:
            logger.error(f"MQTT loop error: {str(e)}")
        finally:
            mqtt_loop.close()

    # Start MQTT loop in separate thread
    mqtt_thread = threading.Thread(target=run_mqtt_loop, daemon=True)
    mqtt_thread.start()

    # Give it a moment to connect
    time.sleep(2)

    return True


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Automatic UV Studio MQTT Client")

    parser.add_argument(
        "--broker-host",
        default=DEFAULT_MQTT_BROKER,
        help=f"MQTT broker host address (default: {DEFAULT_MQTT_BROKER})",
    )

    parser.add_argument(
        "--broker-port",
        type=int,
        default=DEFAULT_MQTT_PORT,
        help=f"MQTT broker port (default: {DEFAULT_MQTT_PORT})",
    )

    parser.add_argument(
        "--topic-prefix",
        default=DEFAULT_TOPIC_PREFIX,
        help=f"MQTT topic prefix (default: {DEFAULT_TOPIC_PREFIX})",
    )

    return parser.parse_args()


def main():
    """Main entry point"""
    global config, mqtt_client, mqtt_loop

    # Parse command line arguments
    args = parse_arguments()

    # Update configuration with CLI arguments
    config = Config(
        broker_host=args.broker_host,
        broker_port=args.broker_port,
        topic_prefix=args.topic_prefix,
    )

    logger.info("Starting automatic-uv-studio MQTT client...")
    logger.info(
        f"Configuration: broker={config.mqtt_broker}:{config.mqtt_port}, prefix={config.topic_prefix}"
    )

    # Setup MQTT connection
    if not setup_mqtt():
        logger.error("Failed to setup MQTT connection. Exiting.")
        return

    logger.info("UV Studio MQTT client is running. Waiting for commands...")

    # Give MQTT time to connect and send initial status
    time.sleep(3)
    publish_status_message("UV Studio MQTT client started and ready", "info")

    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        publish_status_message("UV Studio MQTT client shutting down", "info")

        # Cleanup MQTT
        if mqtt_loop and not mqtt_loop.is_closed():
            if mqtt_client:
                # Schedule disconnect on the MQTT loop
                asyncio.run_coroutine_threadsafe(mqtt_client.disconnect(), mqtt_loop)
            mqtt_loop.call_soon_threadsafe(mqtt_loop.stop)

        time.sleep(1)  # Give time for cleanup


if __name__ == "__main__":
    main()
