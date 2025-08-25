#!/usr/bin/env python3
"""
MQTT Test Client for UV Studio
Supports both paho-mqtt and aMQTT for maximum compatibility
"""

import asyncio
import json
import time
import argparse
import sys

# Try to import both MQTT clients for flexibility
try:
    import paho.mqtt.client as paho_mqtt

    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False

try:
    from amqtt.client import MQTTClient as AmqttClient
    from amqtt.mqtt.constants import QOS_1

    AMQTT_AVAILABLE = True
except ImportError:
    AMQTT_AVAILABLE = False


class MQTTTestClient:
    def __init__(
        self,
        broker_host="localhost",
        broker_port=1883,
        topic_prefix="uv_studio",
        client_type="auto",
    ):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic_prefix = topic_prefix
        self.topic_command = f"{topic_prefix}/command"
        self.topic_status = f"{topic_prefix}/status"

        # Auto-select client type
        if client_type == "auto":
            if PAHO_AVAILABLE:
                self.client_type = "paho"
            elif AMQTT_AVAILABLE:
                self.client_type = "amqtt"
            else:
                raise ImportError("Neither paho-mqtt nor amqtt is available")
        else:
            self.client_type = client_type

        self.client = None
        self.connected = False

    async def connect_amqtt(self):
        """Connect using aMQTT client"""
        try:
            self.client = AmqttClient()
            await self.client.connect(f"mqtt://{self.broker_host}:{self.broker_port}/")
            await self.client.subscribe([(self.topic_status, QOS_1)])
            self.connected = True
            print(
                f"Connected to MQTT broker at {self.broker_host}:{self.broker_port} using aMQTT"
            )
            print(f"Subscribed to {self.topic_status}")
            return True
        except Exception as e:
            print(f"Failed to connect with aMQTT: {str(e)}")
            return False

    def connect_paho(self):
        """Connect using paho-mqtt client"""
        try:
            self.client = paho_mqtt.Client()
            self.client.on_connect = self._on_connect_paho
            self.client.on_message = self._on_message_paho
            self.client.on_disconnect = self._on_disconnect_paho

            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()

            # Wait for connection
            timeout = 5
            while not self.connected and timeout > 0:
                time.sleep(0.1)
                timeout -= 0.1

            return self.connected
        except Exception as e:
            print(f"Failed to connect with paho-mqtt: {str(e)}")
            return False

    def _on_connect_paho(self, client, userdata, flags, rc):
        """Paho MQTT on_connect callback"""
        if rc == 0:
            self.connected = True
            print(
                f"Connected to MQTT broker at {self.broker_host}:{self.broker_port} using paho-mqtt"
            )
            client.subscribe(self.topic_status)
            print(f"Subscribed to {self.topic_status}")
        else:
            print(f"Failed to connect, return code {rc}")

    def _on_disconnect_paho(self, client, userdata, rc):
        """Paho MQTT on_disconnect callback"""
        self.connected = False
        print("Disconnected from MQTT broker")

    def _on_message_paho(self, client, userdata, msg):
        """Paho MQTT on_message callback"""
        self._process_message(msg.topic, msg.payload.decode())

    def _process_message(self, topic, payload):
        """Process received MQTT message"""
        try:
            if topic == self.topic_status:
                data = json.loads(payload)
                timestamp = time.strftime(
                    "%Y-%m-%d %H:%M:%S",
                    time.localtime(data.get("timestamp", time.time())),
                )
                level = data.get("level", "INFO").upper()
                message = data.get("message", "")
                job_running = data.get("print_job_running", False)

                status_indicator = "🔄" if job_running else "⏸️"
                level_indicator = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌"}.get(
                    level, "📝"
                )

                print(
                    f"[{timestamp}] {level_indicator} {level}: {message} {status_indicator}"
                )
            else:
                print(f"Message on {topic}: {payload}")
        except json.JSONDecodeError:
            print(f"Non-JSON message on {topic}: {payload}")
        except Exception as e:
            print(f"Error processing message: {str(e)}")

    async def send_command_amqtt(self, command):
        """Send command using aMQTT"""
        try:
            command_data = {"command": command, "timestamp": time.time()}
            message = json.dumps(command_data)
            await self.client.publish(self.topic_command, message.encode(), qos=QOS_1)
            print(f"✅ Command sent: {command}")
            return True
        except Exception as e:
            print(f"❌ Failed to send command: {str(e)}")
            return False

    def send_command_paho(self, command):
        """Send command using paho-mqtt"""
        try:
            command_data = {"command": command, "timestamp": time.time()}
            message = json.dumps(command_data)
            result = self.client.publish(self.topic_command, message)
            if result.rc == 0:
                print(f"✅ Command sent: {command}")
                return True
            else:
                print(f"❌ Failed to send command, return code: {result.rc}")
                return False
        except Exception as e:
            print(f"❌ Failed to send command: {str(e)}")
            return False

    async def listen_amqtt(self, duration=None):
        """Listen for messages using aMQTT"""
        print("🎧 Listening for status messages (Press Ctrl+C to stop)...")

        start_time = time.time()
        try:
            while True:
                if duration and (time.time() - start_time) > duration:
                    break

                message = await self.client.deliver_message()
                packet = message.publish_packet
                topic = packet.variable_header.topic_name
                payload = packet.payload.data.decode()
                self._process_message(topic, payload)

        except KeyboardInterrupt:
            print("\n⏹️ Stopped listening")
        except Exception as e:
            print(f"❌ Error while listening: {str(e)}")

    def listen_paho(self, duration=None):
        """Listen for messages using paho-mqtt"""
        print("🎧 Listening for status messages (Press Ctrl+C to stop)...")

        try:
            if duration:
                time.sleep(duration)
            else:
                while True:
                    time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n⏹️ Stopped listening")

    async def disconnect(self):
        """Disconnect from broker"""
        if self.client:
            if self.client_type == "amqtt":
                await self.client.disconnect()
            else:
                self.client.loop_stop()
                self.client.disconnect()
            print("📴 Disconnected from broker")


async def main():
    parser = argparse.ArgumentParser(
        description="MQTT Test Client for UV Studio",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  start_12mm_print    Start a 12mm print job
  start_16mm_print    Start a 16mm print job  
  status             Get current printer status
  listen             Listen to status messages
  test               Run a full test sequence

Examples:
  python mqtt_test.py start_12mm_print
  python mqtt_test.py listen --duration 30
  python mqtt_test.py status --broker-host 192.168.1.100
  python mqtt_test.py test --client-type paho
        """,
    )

    parser.add_argument(
        "command", nargs="?", default="listen", help="Command to execute"
    )

    parser.add_argument(
        "--broker-host",
        default="localhost",
        help="MQTT broker host (default: localhost)",
    )

    parser.add_argument(
        "--broker-port", type=int, default=1883, help="MQTT broker port (default: 1883)"
    )

    parser.add_argument(
        "--topic-prefix",
        default="uv_studio",
        help="MQTT topic prefix (default: uv_studio)",
    )

    parser.add_argument(
        "--client-type",
        choices=["auto", "paho", "amqtt"],
        default="auto",
        help="MQTT client type to use (default: auto)",
    )

    parser.add_argument(
        "--duration", type=int, help="Duration for listen command in seconds"
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Show available clients
    if args.verbose:
        print(f"📚 Available MQTT clients:")
        print(f"  - paho-mqtt: {'✅' if PAHO_AVAILABLE else '❌'}")
        print(f"  - aMQTT: {'✅' if AMQTT_AVAILABLE else '❌'}")
        print()

    try:
        # Create client
        client = MQTTTestClient(
            broker_host=args.broker_host,
            broker_port=args.broker_port,
            topic_prefix=args.topic_prefix,
            client_type=args.client_type,
        )

        # Connect
        if client.client_type == "amqtt":
            if not await client.connect_amqtt():
                return 1
        else:
            if not client.connect_paho():
                return 1

        # Execute command
        if args.command == "listen":
            if client.client_type == "amqtt":
                await client.listen_amqtt(args.duration)
            else:
                client.listen_paho(args.duration)

        elif args.command == "test":
            print("🧪 Running test sequence...")

            # Test status command
            print("\n1️⃣ Testing status command...")
            if client.client_type == "amqtt":
                await client.send_command_amqtt("status")
                await asyncio.sleep(2)
            else:
                client.send_command_paho("status")
                time.sleep(2)

            # Test 12mm print command
            print("\n2️⃣ Testing 12mm print command...")
            if client.client_type == "amqtt":
                await client.send_command_amqtt("start_12mm_print")
                await asyncio.sleep(3)
            else:
                client.send_command_paho("start_12mm_print")
                time.sleep(3)

            # Listen for a bit
            print("\n3️⃣ Listening for responses...")
            if client.client_type == "amqtt":
                await client.listen_amqtt(5)
            else:
                client.listen_paho(5)

        elif args.command in ["start_12mm_print", "start_16mm_print", "status"]:
            if client.client_type == "amqtt":
                await client.send_command_amqtt(args.command)
                # Listen for responses
                await client.listen_amqtt(5)
            else:
                client.send_command_paho(args.command)
                # Listen for responses
                client.listen_paho(5)
        else:
            print(f"❌ Unknown command: {args.command}")
            print(
                "Valid commands: start_12mm_print, start_16mm_print, status, listen, test"
            )
            return 1

        # Disconnect
        await client.disconnect()
        return 0

    except KeyboardInterrupt:
        print("\n⏹️ Application terminated by user")
        return 0
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return 1


if __name__ == "__main__":
    if not PAHO_AVAILABLE and not AMQTT_AVAILABLE:
        print("❌ Error: Neither paho-mqtt nor amqtt is available")
        print("Install one of them with:")
        print("  uv add paho-mqtt")
        print("  uv add amqtt")
        sys.exit(1)

    sys.exit(asyncio.run(main()))
