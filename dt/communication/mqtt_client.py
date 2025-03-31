import json
from ast import List

import paho.mqtt.client as mqtt
from typing_extensions import Any, Callable

from dt.utils import SensorData, get_logger


class MQTTClient:
    def __init__(
        self, hostname: str = "localhost", port: int = 1883, id: str = "digital_twin"
    ) -> None:
        """Initialize the MQTT client.

        Parameters
        ----------
        hostname : str
            Name of the broker to connect to.
        port : int
            Port number to connect to.
        id : str
            Client ID to use for the connection.
        """
        self.client = mqtt.Client(client_id=id)
        self.hostname = hostname
        self.port = port
        self.topic_callbacks: dict[str, list[Callable]] = {}
        self.logger = get_logger(__name__)

        # Set up callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    def connect(self):
        """Connect to the MQTT broker"""
        try:
            self.client.connect(self.hostname, self.port)
            self.client.loop_start()  # Start the background thread
            self.logger.info(f"Connected to MQTT broker at {self.hostname}:{self.port}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT broker: {e}")
            return False

    def disconnect(self):
        """Disconnect from the MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()
        self.logger.info("Disconnected from MQTT broker")

    def publish(self, topic: str, payload: SensorData, qos: int = 1):
        """Publish a message to a topic"""
        try:
            message = payload.to_json()
            result = self.client.publish(topic, message, qos=qos)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.logger.debug(f"Published to {topic}: {payload}")
                return True
            else:
                self.logger.error(f"Failed to publish to {topic}: {mqtt.error_string(result.rc)}")
                return False
        except Exception as e:
            self.logger.error(f"Error publishing message: {e}")
            return False

    def subscribe(self, topic: str, callback: Callable, qos: int = 1):
        """Subscribe to a topic with a callback"""
        if topic in self.topic_callbacks:
            self.topic_callbacks[topic].append(callback)
        else:
            self.topic_callbacks[topic] = [callback]
        result = self.client.subscribe(topic, qos)
        if result[0] == mqtt.MQTT_ERR_SUCCESS:
            self.logger.info(f"Subscribed to {topic}")
            return True
        else:
            self.logger.error(f"Failed to subscribe to {topic}")
            return False

    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when client connects to the broker"""
        if rc == 0:
            self.logger.info("Connected to MQTT Broker")
            # Re-subscribe to all topics
            for topic in self.topic_callbacks.keys():
                self.client.subscribe(topic)
        else:
            self.logger.error(f"Failed to connect to broker with code {rc}")

    def _on_message(self, client, userdata, msg):
        """Callback for when a message is received"""
        try:
            topic = msg.topic
            if not SensorData.validate_json(msg.payload.decode()):
                self.logger.error(f"Received malformed JSON on {topic}")
                return
            payload = SensorData.from_json(msg.payload.decode())

            self.logger.debug(f"Received message on {topic}: {payload}")

            # Call the appropriate callback for this topic
            if topic in self.topic_callbacks:
                for callback in self.topic_callbacks[topic]:
                    callback(payload)
                # self.topic_callbacks[topic](payload)
        except json.JSONDecodeError:
            self.logger.error(f"Received malformed JSON on {msg.topic}")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback for when client disconnects from the broker"""
        if rc != 0:
            self.logger.warning(f"Unexpected disconnect from broker: {rc}")
