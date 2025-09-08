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
import signal
from amqtt.client import MQTTClient
from amqtt.mqtt.constants import QOS_1, QOS_2
from amqtt.errors import ClientError

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
mqtt_broker_process = None
broker_config = None
event_loop = None
low_ink = False


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


class MQTTLogHandler(logging.Handler):
    """Custom logging handler that sends log messages to MQTT"""

    def __init__(self, mqtt_client, topic):
        super().__init__()
        self.mqtt_client = mqtt_client
        self.topic = topic

    def emit(self, record):
        if (
            self.mqtt_client
            and hasattr(self.mqtt_client, "_connected")
            and self.mqtt_client._connected
        ):
            try:
                log_message = {
                    "timestamp": time.time(),
                    "level": record.levelname,
                    "message": record.getMessage(),
                    "module": record.module,
                }
                # Schedule async publish in the background
                asyncio.create_task(self._async_publish(json.dumps(log_message)))
            except Exception:
                pass  # Don't let MQTT failures break logging

    async def _async_publish(self, message):
        try:
            await self.mqtt_client.publish(self.topic, message.encode())
        except Exception:
            pass


# Configure logging
def setup_logging():
    """Setup logging with both console and MQTT handlers"""
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
    window = pwc.getWindowsWithTitle("eufy", pwc.Re.CONTAINS)
    if not window and not window[0]:
        return False
    window[0].activate(wait=True)

    # get the window size and position
    return window[0].rect


def stop_print():
    window_rect = prepare_window()

    if not window_rect:
        error_msg = f"Could not prepare window"
        print(error_msg)
        logger.error(error_msg)
        publish_status_message(error_msg, "error")
        return False

    stop = Stop(window_rect=window_rect)
    if not stop.run():
        error_msg = f"Could not stop the task"
        print(error_msg)
        logger.error(error_msg)
        publish_status_message(error_msg, "error")
        return False


def start_print(canvas_index=0, publish_control_message=None, should_scan_tray=False):
    global stop_print_event
    global low_ink

    window_rect = prepare_window()

    prefix = "[12mm] " if canvas_index == 0 else "[16mm] "

    prepare_msg = f"{prefix}Preparing eufy Make Studio"
    print(prepare_msg)
    logger.info(prepare_msg)
    publish_status_message(prepare_msg, "info")

    # Check for stop signal
    if stop_print_event.is_set():
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
        return False

    check_if_moisturized = CheckIfShouldMoisturize(window_rect=window_rect)
    if not check_if_moisturized.run():
        error_msg = f"{prefix}Printer not moisturized"
        print(error_msg)
        logger.error(error_msg)
        publish_status_message(error_msg, "error")
        return False

    # Check for stop signal
    if stop_print_event.is_set():
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
        return False

    # Check for low ink
    check_if_low_ink = CheckIfLowInk(window_rect=window_rect)
    low_ink = not check_if_low_ink.run()

    # Scan the tray
    if should_scan_tray:
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
    else:
        select_zeropoint = SelectZeroPointAlignment(window_rect=window_rect)
        if not select_zeropoint.run(canvas_index=canvas_index):
            error_msg = f"{prefix}Failed to select zero point alignment"
            print(error_msg)
            logger.error(error_msg)
            publish_status_message(error_msg, "error")
            return False

    # Check for stop signal
    if stop_print_event.is_set():
        return False

    # Print
    loggableName = "12mm" if canvas_index == 0 else "16mm"
    start_msg = f"{prefix}Starting {loggableName} print"
    print(start_msg)
    logger.info(start_msg)
    publish_status_message(start_msg, "info")
    start_print = StartPrint(
        window_rect=window_rect, publish_control_message=publish_control_message
    )
    if not start_print.run(canvas_index=canvas_index):
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


def log_stop():
    logger.info(f"[{print_type}] print was stopped")
    publish_status_message(f"[{print_type}] print was stopped", "info")


def start_print_async(canvas_index, print_type):
    """Run the print workflow asynchronously"""
    global current_print_thread, stop_print_event

    # Set to False will use the zero reference printing without prescannung
    # True will scan and print without using the reference feature.
    should_scan_tray = False

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
        start_msg = f"Starting {print_type} print"
        logger.info(start_msg)
        print(start_msg)
        publish_status_message(start_msg, "info")

        if stop_print_event.is_set():
            log_stop()
            return False

        success = start_print(
            canvas_index=canvas_index,
            publish_control_message=publish_control_message,
            should_scan_tray=should_scan_tray,
        )

        if stop_print_event.is_set():
            log_stop()
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


def publish_status_message(message, level="info"):
    """Publish a status message to MQTT (sync wrapper)"""
    global event_loop

    if event_loop and event_loop.is_running():
        # Schedule the coroutine to run in the event loop from another thread
        asyncio.run_coroutine_threadsafe(
            publish_status_message_async(message, level), event_loop
        )
    else:
        logger.warning("No event loop available for publishing status message")


def publish_control_message(action):
    """Publish a control message to MQTT (sync wrapper)"""
    global event_loop

    if event_loop and event_loop.is_running():
        # Schedule the coroutine to run in the event loop from another thread
        asyncio.run_coroutine_threadsafe(
            publish_control_message_async(action), event_loop
        )
    else:
        logger.warning("No event loop available for publishing control message")


async def publish_control_message_async(action):
    """Publish a control message to MQTT asynchronously"""
    control_message = {"action": action, "timestamp": time.time()}
    try:
        await mqtt_client.publish(
            config.topic_control, json.dumps(control_message).encode(), qos=QOS_1
        )
        logger.info(f"Published control message: {action}")
    except Exception as e:
        logger.error(f"Failed to publish control message: {str(e)}")


async def mqtt_message_handler():
    """Handle incoming MQTT messages"""
    global mqtt_client

    try:
        while True:
            message = await mqtt_client.deliver_message()
            packet = message.publish_packet
            topic = packet.variable_header.topic_name
            payload = packet.payload.data.decode()

            logger.info(f"Received MQTT message on topic {topic}: {payload}")

            try:
                payload_json = json.loads(payload)

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
                        await publish_status_message_async(
                            f"Unknown command: {command}", "warning"
                        )

            except json.JSONDecodeError:
                logger.error("Failed to decode JSON message")
                await publish_status_message_async(
                    "Failed to decode JSON message", "error"
                )

    except ClientError as e:
        logger.error(f"MQTT Client exception: {str(e)}")
    except Exception as e:
        logger.error(f"Error in MQTT message handler: {str(e)}")


async def publish_status_message_async(message, level="info"):
    """Publish a status message to MQTT asynchronously"""
    status_message = {
        "timestamp": time.time(),
        "level": level,
        "message": message,
        "low_ink": low_ink,
        "print_job_running2": current_print_thread and current_print_thread.is_alive(),
    }
    try:
        await mqtt_client.publish(
            config.topic_status, json.dumps(status_message).encode(), qos=QOS_1
        )
    except Exception as e:
        logger.error(f"Failed to publish MQTT message: {str(e)}")


def handle_start_print_command(print_type, canvas_index, should_scan_tray=False):
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
    else:
        logger.warning("No print job is currently running")


async def setup_mqtt():
    """Setup MQTT client and connect to broker"""
    global mqtt_client

    try:
        mqtt_client = MQTTClient()

        logger.info(
            f"Connecting to MQTT broker at {config.mqtt_broker}:{config.mqtt_port}"
        )
        await mqtt_client.connect(f"mqtt://{config.mqtt_broker}:{config.mqtt_port}/")

        # Subscribe to command topic
        await mqtt_client.subscribe([(config.topic_command, QOS_1)])
        logger.info(f"Subscribed to {config.topic_command}")

        logger.info("Connected to MQTT broker")
        await publish_status_message_async("UV Studio connected to MQTT broker", "info")

        return True
    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {str(e)}")
        return False


async def start_mqtt_broker(host="localhost", port=1883):
    """Start an embedded MQTT broker using aMQTT"""
    try:
        from amqtt.broker import Broker

        logger.info(f"Starting embedded MQTT broker on {host}:{port}")

        # Handle Windows binding issues
        if host == "0.0.0.0":
            # On Windows, try using the actual IP address or localhost
            import socket

            try:
                # Get the local IP address
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                host = local_ip
                logger.info(f"Using local IP address for binding: {host}")
            except Exception:
                host = "localhost"
                logger.info("Falling back to localhost for binding")

        # Configuration for the broker
        broker_config = {
            "listeners": {
                "default": {
                    "type": "tcp",
                    "bind": f"{host}:{port}",
                    "max_connections": 50,
                }
            },
        }

        broker = Broker(config=broker_config)

        try:
            await broker.start()
            logger.info(f"MQTT broker successfully started on {host}:{port}")
            # Keep the broker running
            await asyncio.sleep(float("inf"))
        except asyncio.CancelledError:
            logger.info("Broker shutdown requested")
        finally:
            await broker.shutdown()

    except Exception as e:
        logger.error(f"Failed to start MQTT broker: {str(e)}")
        return False


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

    parser.add_argument(
        "--start-broker",
        action="store_true",
        help="Start an embedded MQTT broker before connecting",
    )

    parser.add_argument(
        "--broker-only",
        action="store_true",
        help="Only start the MQTT broker (don't start the UV Studio client)",
    )

    return parser.parse_args()


async def async_main():
    """Async main function for MQTT client"""
    global config, event_loop

    # Set the global event loop reference
    event_loop = asyncio.get_event_loop()

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

    # Start embedded MQTT broker if requested
    if args.start_broker or args.broker_only:
        logger.info("Starting embedded MQTT broker...")
        try:
            # Start broker in background task
            broker_task = asyncio.create_task(
                start_mqtt_broker(config.mqtt_broker, config.mqtt_port)
            )

            # Give the broker time to start
            await asyncio.sleep(2)
            logger.info(
                f"MQTT broker started on {config.mqtt_broker}:{config.mqtt_port}"
            )

        except Exception as e:
            logger.error(f"Failed to start MQTT broker: {str(e)}")
            if args.broker_only:
                return

    # If broker-only mode, just keep the broker running
    if args.broker_only:
        logger.info("Running in broker-only mode. Press Ctrl+C to stop.")
        try:
            await asyncio.sleep(float("inf"))
        except KeyboardInterrupt:
            logger.info("Shutting down broker...")
        return

    # Setup MQTT connection
    if not await setup_mqtt():
        logger.error("Failed to setup MQTT connection. Exiting.")
        return

    # Start message handler task
    message_handler_task = asyncio.create_task(mqtt_message_handler())

    logger.info("UV Studio MQTT client is running. Waiting for commands...")
    await publish_status_message_async(
        "UV Studio MQTT client started and ready", "info"
    )

    try:
        # Keep the main loop alive
        await asyncio.sleep(float("inf"))
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await publish_status_message_async(
            "UV Studio MQTT client shutting down", "info"
        )
        message_handler_task.cancel()
        if mqtt_client:
            await mqtt_client.disconnect()


def main():
    """Main entry point"""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    global config

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

    # Start embedded MQTT broker if requested
    if args.start_broker or args.broker_only:
        logger.info("Starting embedded MQTT broker...")
        try:
            # Start broker in a separate thread
            import threading

            def run_broker():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    start_mqtt_broker(config.mqtt_broker, config.mqtt_port)
                )

            broker_thread = threading.Thread(target=run_broker, daemon=True)
            broker_thread.start()

            # Give the broker time to start
            time.sleep(2)
            logger.info(
                f"MQTT broker started on {config.mqtt_broker}:{config.mqtt_port}"
            )

        except Exception as e:
            logger.error(f"Failed to start MQTT broker: {str(e)}")
            if args.broker_only:
                return

    # If broker-only mode, just keep the broker running
    if args.broker_only:
        logger.info("Running in broker-only mode. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down broker...")
        return

    # Setup MQTT connection
    if not setup_mqtt():
        logger.error("Failed to setup MQTT connection. Exiting.")
        return

    # Start MQTT loop in a separate thread
    mqtt_client.loop_start()

    logger.info("UV Studio MQTT client is running. Waiting for commands...")
    publish_status_message("UV Studio MQTT client started and ready", "info")

    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        publish_status_message("UV Studio MQTT client shutting down", "info")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()


if __name__ == "__main__":
    main()
