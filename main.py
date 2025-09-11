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
DEFAULT_WINDOW_TITLE = "eufy"
DEFAULT_RETINA = True

# Global variables
print_lock = threading.Lock()
current_print_thread = None
current_print_type = False  # False, '12mm', '16mm', 'stopping_12mm', 'stopping_16mm', 'error_12mm', or 'error_16mm'
stop_print_event = threading.Event()
mqtt_client = None
low_ink = False
mqtt_loop = None
mqtt_connected = False
mqtt_reconnect_delay = 5  # seconds


class Config:
    """Configuration class to hold MQTT settings"""

    def __init__(
        self,
        broker_host=DEFAULT_MQTT_BROKER,
        broker_port=DEFAULT_MQTT_PORT,
        topic_prefix=DEFAULT_TOPIC_PREFIX,
        window_title=DEFAULT_WINDOW_TITLE,
        retina=DEFAULT_RETINA,
    ):
        self.mqtt_broker = broker_host
        self.mqtt_port = broker_port
        self.topic_prefix = topic_prefix
        self.topic_command = f"{topic_prefix}/command"
        self.topic_status = f"{topic_prefix}/status"
        self.topic_control = f"{topic_prefix}/control"
        self.window_title = window_title
        self.retina = retina
        self.image_path = "images" if retina else "images/non-retina"


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
    windows = pwc.getWindowsWithTitle(
        config.window_title, condition=pwc.Re.CONTAINS, flags=pwc.Re.IGNORECASE
    )
    # If no window is found, log available titles to help debugging
    if not windows:
        try:
            titles = pwc.getAllTitles()
            logger.error(
                f"No window found containing '{config.window_title}'. Open windows: "
                + ", ".join(titles[:20])
            )
        except Exception:
            logger.error(f"No window found containing '{config.window_title}'.")
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

    if not window_rect:
        error_msg = f"Could not prepare window"
        print(error_msg)
        logger.error(error_msg)
        return False

    # reset the screen
    stop = Stop(
        window_rect=window_rect, is_retina=config.retina, image_path=config.image_path
    )
    if not stop.run():
        error_msg = f"Could not stop"
        print(error_msg)
        logger.error(error_msg)
        return False


def start_print(
    canvas_index=0,
    should_scan_tray=False,
    publish_control_message=None,
    print_type=None,
):
    global stop_print_event
    global low_ink
    global current_print_type

    window_rect = prepare_window()

    if not window_rect:
        error_msg = f"Could not prepare window"
        print(error_msg)
        logger.error(error_msg)
        return False

    prefix = "[12mm] " if canvas_index == 0 else "[16mm] "

    prepare_msg = f"{prefix}Preparing eufy Make Studio"
    print(prepare_msg)
    logger.info(prepare_msg)

    # Check for stop signal
    if stop_print_event.is_set():
        if print_type:
            current_print_type = f"stopping_{print_type}"
        logger.info(f"{prefix}Print stopped during preparation")
        return False

    if not window_rect:
        error_msg = f"{prefix}Could not prepare window"
        print(error_msg)
        logger.error(error_msg)
        return False

    # reset the screen
    reset_ui = ResetUIWorkflow(
        window_rect=window_rect, is_retina=config.retina, image_path=config.image_path
    )
    if not reset_ui.run():
        error_msg = f"{prefix}Could not reset the UI"
        print(error_msg)
        logger.error(error_msg)
        return False

    # Check for stop signal
    if stop_print_event.is_set():
        if print_type:
            current_print_type = f"stopping_{print_type}"
        logger.info(f"{prefix}Print stopped during UI reset")
        return False

    # check if printer online
    check_if_online = CheckIfOnline(
        window_rect=window_rect, is_retina=config.retina, image_path=config.image_path
    )
    if not check_if_online.run():
        error_msg = f"{prefix}Printer not online"
        print(error_msg)
        logger.error(error_msg)
        return False

        # Check for stop signal
    if stop_print_event.is_set():
        if print_type:
            current_print_type = f"stopping_{print_type}"
        return False

    check_if_moisturized = CheckIfShouldMoisturize(window_rect=window_rect)
    if not check_if_moisturized.run():
        error_msg = f"{prefix}Printer not moisturized"
        print(error_msg)
        logger.error(error_msg)
        return False

    # Check for stop signal
    if stop_print_event.is_set():
        if print_type:
            current_print_type = f"stopping_{print_type}"
        logger.info(f"{prefix}Print stopped during online check")
        return False

    # Make sure the printer is idle
    check_if_idle = CheckIfIdle(
        window_rect=window_rect, is_retina=config.retina, image_path=config.image_path
    )
    if not check_if_idle.run():
        error_msg = f"{prefix}Printer not idle"
        print(error_msg)
        logger.error(error_msg)
        return False

    # Check for stop signal
    if stop_print_event.is_set():
        if print_type:
            current_print_type = f"stopping_{print_type}"
        logger.info(f"{prefix}Print stopped during idle check")
        return False

    # Check for low ink
    check_if_low_ink = CheckIfLowInk(window_rect=window_rect)
    low_ink = not check_if_low_ink.run()

    # Scan the tray
    if should_scan_tray:
        scan_msg = f"{prefix}Scanning the tray"
        print(scan_msg)
        logger.info(scan_msg)
        scan_tray = ScanTray(
            window_rect=window_rect,
            is_retina=config.retina,
            image_path=config.image_path,
        )
        if not scan_tray.run(canvas_index=canvas_index):
            error_msg = f"{prefix}Failed to scan tray"
            print(error_msg)
            logger.error(error_msg)
            return False
    else:
        select_zeropoint = SelectZeroPointAlignment(
            window_rect=window_rect, image_path=config.image_path
        )
        if not select_zeropoint.run(canvas_index=canvas_index):
            error_msg = f"{prefix}Failed to select zero point alignment"
            print(error_msg)
            logger.error(error_msg)
            return False

    # Check for stop signal
    if stop_print_event.is_set():
        if print_type:
            current_print_type = f"stopping_{print_type}"
        logger.info(f"{prefix}Print stopped during tray scan")
        return False

    # Print
    loggableName = "12mm" if canvas_index == 0 else "16mm"
    start_msg = f"{prefix}Starting {loggableName} print"
    print(start_msg)
    logger.info(start_msg)
    start_print_workflow = StartPrint(
        window_rect=window_rect,
        publish_control_message=publish_control_message,
        is_retina=config.retina,
        image_path=config.image_path,
        logger=logger,
    )
    if not start_print_workflow.run(canvas_index=canvas_index):
        error_msg = f"{prefix}Failed to print"
        print(error_msg)
        logger.error(error_msg)
        return False

    # Check for stop signal
    if stop_print_event.is_set():
        if print_type:
            current_print_type = f"stopping_{print_type}"
        logger.info(f"{prefix}Print stopped during print execution")
        return False

    success_msg = f"{prefix}Print completed successfully"
    print(success_msg)
    logger.info(success_msg)
    return True


def start_print_async(canvas_index, print_type, publish_control_message=None):
    """Run the print workflow asynchronously"""
    global current_print_thread, stop_print_event, current_print_type

    # Check if we can acquire the lock (non-blocking)
    if not print_lock.acquire(blocking=False):
        error_msg = (
            f"Cannot start {print_type} print - another print job is already running"
        )
        logger.warning(error_msg)
        print(error_msg)
        return False

    try:
        # Clear any previous stop signal
        stop_print_event.clear()

        # Set current print type for ping system
        current_print_type = print_type

        current_print_thread = threading.current_thread()
        start_msg = f"Starting {print_type} print (canvas_index={canvas_index})"
        logger.info(start_msg)
        print(start_msg)

        # Check for stop signal before starting
        if stop_print_event.is_set():
            logger.info(f"{print_type} print was stopped before starting")
            return False

        success = start_print(
            canvas_index=canvas_index,
            publish_control_message=publish_control_message,
            print_type=print_type,
        )

        # Check for stop signal after print attempt
        if stop_print_event.is_set():
            logger.info(f"{print_type} print was stopped")
            current_print_type = f"stopping_{print_type}"  # Set stopping state
            stop_print()  # Call the stop_print function to handle cleanup
            current_print_type = False  # Reset to idle after stop is complete
            return False

        if success:
            success_msg = f"Completed {print_type} print successfully"
            logger.info(success_msg)
            print(success_msg)
            current_print_type = False  # Reset to idle on success
        else:
            error_msg = f"Failed to complete {print_type} print"
            logger.error(error_msg)
            print(error_msg)
            current_print_type = (
                f"error_{print_type}"  # Set error state with print type
            )

        return success
    except Exception as e:
        error_msg = f"Error during {print_type} print: {str(e)}"
        logger.error(error_msg)
        print(error_msg)
        current_print_type = (
            f"error_{print_type}"  # Set error state with print type on exception
        )
        return False
    finally:
        current_print_thread = None
        print_lock.release()
        finish_msg = f"{print_type} print thread finished"
        logger.info(finish_msg)
        print(finish_msg)


async def publish_ping():
    """Publish regular ping with current print status"""
    global mqtt_client, mqtt_connected, current_print_type

    if mqtt_client and mqtt_connected:
        ping_message = {"print_running": current_print_type}

        try:
            await mqtt_client.publish(
                config.topic_status, json.dumps(ping_message).encode(), qos=QOS_1
            )
        except Exception as e:
            logger.error(f"Failed to publish ping: {str(e)}")
            mqtt_connected = False
            # Trigger reconnection
            asyncio.create_task(mqtt_reconnect())


async def ping_loop():
    """Send ping every second"""
    while True:
        try:
            await asyncio.sleep(1)
            if mqtt_connected:
                await publish_ping()
        except Exception as e:
            logger.error(f"Error in ping loop: {str(e)}")
            await asyncio.sleep(1)


def publish_control_message(action):
    """Publish a control message to MQTT"""
    global mqtt_loop, mqtt_connected

    if mqtt_loop and not mqtt_loop.is_closed() and mqtt_connected:
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
    global mqtt_client, mqtt_connected

    if mqtt_client:
        try:
            await mqtt_client.publish(
                config.topic_control, json.dumps(control_message).encode(), qos=QOS_1
            )
            logger.info(f"Published control message: {control_message['action']}")
        except Exception as e:
            logger.error(f"Failed to publish control message: {str(e)}")
            mqtt_connected = False
            # Trigger reconnection
            asyncio.create_task(mqtt_reconnect())


def handle_start_print_command(print_type, canvas_index):
    """Handle start print command from MQTT"""
    # Check if another print is already running
    if current_print_thread and current_print_thread.is_alive():
        error_msg = (
            f"Cannot start {print_type} print - another print job is already running"
        )
        logger.warning(error_msg)
        return

    # Start the print job in a separate thread
    thread = threading.Thread(
        target=start_print_async,
        args=(canvas_index, print_type),
        kwargs={"publish_control_message": publish_control_message},
        daemon=True,
    )
    thread.start()

    success_msg = f"{print_type} print job started"
    logger.info(success_msg)


def handle_status_command():
    """Handle status request command from MQTT"""
    is_running = current_print_thread and current_print_thread.is_alive()
    status_msg = f"Print job running: {is_running}"
    logger.info(status_msg)


def handle_stop_command():
    """Handle stop command from MQTT"""
    global stop_print_event, current_print_type

    if current_print_thread and current_print_thread.is_alive():
        # Signal the print thread to stop
        stop_print_event.set()

        # Call stop_print to handle any immediate UI cleanup
        stop_print()

        logger.info("Print job stop signal sent")
    else:
        # If no print is running but we're in error or stopping state, clear it
        if current_print_type and (
            current_print_type.startswith("error_")
            or current_print_type.startswith("stopping_")
        ):
            current_print_type = False
            logger.info("Cleared error/stopping state")
        else:
            logger.warning("No print job is currently running")


def handle_clear_error_command():
    """Handle clear error command from MQTT"""
    global current_print_type

    if current_print_type and (
        current_print_type.startswith("error_")
        or current_print_type.startswith("stopping_")
    ):
        current_print_type = False
        logger.info("Error/stopping state cleared via command")
    else:
        logger.info(f"Current state is '{current_print_type}', no error to clear")


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
            elif command == "clear_error":
                handle_clear_error_command()
            else:
                logger.warning(f"Unknown command: {command}")

    except json.JSONDecodeError:
        logger.error("Failed to decode JSON message")
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")


async def mqtt_reconnect():
    """Handle MQTT reconnection"""
    global mqtt_client, mqtt_connected

    if mqtt_connected:
        return  # Already connected

    logger.info("Attempting to reconnect to MQTT broker...")

    max_retries = 5
    retry_count = 0

    while retry_count < max_retries and not mqtt_connected:
        try:
            await asyncio.sleep(mqtt_reconnect_delay)

            # Close existing client if any
            if mqtt_client:
                try:
                    await mqtt_client.disconnect()
                except:
                    pass

            # Create new client and connect
            mqtt_client = MQTTClient()
            broker_url = f"mqtt://{config.mqtt_broker}:{config.mqtt_port}"
            await mqtt_client.connect(broker_url)

            # Wait a moment for session to be properly initialized
            await asyncio.sleep(0.5)

            # Verify session is properly connected (aMQTT uses transitions state machine)
            if not mqtt_client.session:
                raise Exception("Session not initialized after reconnect")

            # Check if session is in connected state using transitions
            if (
                hasattr(mqtt_client.session, "is_connected")
                and not mqtt_client.session.is_connected()
            ):
                raise Exception("Session not in connected state after reconnect")

            # Resubscribe to topics
            await mqtt_client.subscribe([(config.topic_command, QOS_1)])

            mqtt_connected = True
            logger.info("Successfully reconnected to MQTT broker")

            # Restart message handler
            asyncio.create_task(mqtt_message_handler())
            break

        except Exception as e:
            retry_count += 1
            logger.error(f"Reconnection attempt {retry_count} failed: {str(e)}")
            if retry_count >= max_retries:
                logger.error("Max reconnection attempts reached, giving up")
                break


async def mqtt_message_handler():
    """Async message handler for aMQTT with reconnection logic"""
    global mqtt_client, mqtt_connected

    try:
        while mqtt_connected:
            try:
                # Check if client and session are properly initialized
                if (
                    not mqtt_client
                    or not hasattr(mqtt_client, "session")
                    or not mqtt_client.session
                ):
                    logger.warning(
                        "MQTT client session not initialized, stopping message handler"
                    )
                    mqtt_connected = False
                    asyncio.create_task(mqtt_reconnect())
                    break

                # Check if session is in connected state using transitions
                if (
                    hasattr(mqtt_client.session, "is_connected")
                    and not mqtt_client.session.is_connected()
                ):
                    logger.warning(
                        "MQTT session not connected, stopping message handler"
                    )
                    mqtt_connected = False
                    asyncio.create_task(mqtt_reconnect())
                    break

                message = await mqtt_client.deliver_message()

                # Check if message is None (can happen on disconnection/timeout)
                if message is None:
                    logger.warning("Received None message, continuing...")
                    continue

                # Check if message has the expected structure
                if (
                    not hasattr(message, "publish_packet")
                    or message.publish_packet is None
                ):
                    logger.warning("Received malformed message")
                    continue

                packet = message.publish_packet

                # Check if packet has the expected structure
                if not hasattr(packet, "variable_header") or not hasattr(
                    packet, "payload"
                ):
                    logger.warning("Received packet with missing data")
                    continue

                topic = packet.variable_header.topic_name
                payload = packet.payload.data

                # Handle message in background to avoid blocking
                asyncio.create_task(handle_mqtt_message(topic, payload))

            except Exception as e:
                logger.error(f"Error receiving MQTT message: {str(e)}")
                mqtt_connected = False
                # Trigger reconnection
                asyncio.create_task(mqtt_reconnect())
                break

    except Exception as e:
        logger.error(f"Error in MQTT message handler: {str(e)}")
        mqtt_connected = False
        # Trigger reconnection
        asyncio.create_task(mqtt_reconnect())


async def setup_mqtt_async():
    """Setup aMQTT client and connect to broker"""
    global mqtt_client, mqtt_connected

    try:
        mqtt_client = MQTTClient()

        broker_url = f"mqtt://{config.mqtt_broker}:{config.mqtt_port}"
        logger.info(f"Connecting to MQTT broker at {broker_url}")

        await mqtt_client.connect(broker_url)

        # Wait a moment for session to be properly initialized
        await asyncio.sleep(0.5)

        # Verify session is properly connected (aMQTT uses transitions state machine)
        if not mqtt_client.session:
            raise Exception("Session not initialized after connect")

        # Check if session is in connected state using transitions
        if (
            hasattr(mqtt_client.session, "is_connected")
            and not mqtt_client.session.is_connected()
        ):
            raise Exception("Session not in connected state")

        mqtt_connected = True
        logger.info("Connected to MQTT broker")

        # Subscribe to command topic
        await mqtt_client.subscribe([(config.topic_command, QOS_1)])
        logger.info(f"Subscribed to {config.topic_command}")

        # Start message handler and ping loop
        asyncio.create_task(mqtt_message_handler())
        asyncio.create_task(ping_loop())

        return True

    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {str(e)}")
        mqtt_connected = False
        # Schedule reconnection attempt
        asyncio.create_task(mqtt_reconnect())
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
            # Start periodic connection check
            mqtt_loop.create_task(mqtt_keepalive())
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


async def mqtt_keepalive():
    """Periodic connection check and reconnection if needed"""
    global mqtt_connected

    while True:
        try:
            await asyncio.sleep(5)  # Check every 30 seconds

            if not mqtt_connected:
                logger.warning("MQTT connection lost, attempting reconnection...")
                asyncio.create_task(mqtt_reconnect())

        except Exception as e:
            logger.error(f"Error in MQTT keepalive: {str(e)}")


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
        "--window-title",
        default=DEFAULT_WINDOW_TITLE,
        help=f"Substring of the target app window title (default: {DEFAULT_WINDOW_TITLE})",
    )

    parser.add_argument(
        "--retina",
        action="store_true",
        default=DEFAULT_RETINA,
        help="Use retina mode (default: True)",
    )

    parser.add_argument(
        "--no-retina",
        action="store_false",
        dest="retina",
        help="Use non-retina mode",
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
        window_title=args.window_title,
        retina=args.retina,
    )

    logger.info("Starting automatic-uv-studio MQTT client...")
    logger.info(
        f"Configuration: broker={config.mqtt_broker}:{config.mqtt_port}, prefix={config.topic_prefix}, window_title~='{config.window_title}', retina={config.retina}, images={config.image_path}"
    )

    # Setup MQTT connection
    if not setup_mqtt():
        logger.error("Failed to setup MQTT connection. Exiting.")
        return

    logger.info("UV Studio MQTT client is running. Waiting for commands...")

    # Give MQTT time to connect and send initial status
    time.sleep(3)

    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")

        # Cleanup MQTT
        if mqtt_loop and not mqtt_loop.is_closed():
            if mqtt_client:
                # Schedule disconnect on the MQTT loop
                asyncio.run_coroutine_threadsafe(mqtt_client.disconnect(), mqtt_loop)
            mqtt_loop.call_soon_threadsafe(mqtt_loop.stop)

        time.sleep(1)  # Give time for cleanup


if __name__ == "__main__":
    main()
