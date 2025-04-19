import json
import threading
import time
from abc import ABC, abstractmethod

import paho.mqtt.client as mqtt
from kafka import KafkaConsumer, KafkaProducer
from typing_extensions import Callable, override

from dt.utils import SensorData, get_logger


class MessagingService(ABC):
    """Abstract base class for messaging services like MQTT, Kafka, etc."""

    @abstractmethod
    def connect(self) -> bool:
        """Connect to the messaging service"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the messaging service"""
        pass

    @abstractmethod
    def publish(self, topic: str, payload: SensorData, **kwargs) -> bool:
        """Publish a message to a topic"""
        pass

    @abstractmethod
    def subscribe(self, topic: str, callback: Callable, **kwargs) -> bool:
        """Subscribe to a topic with a callback"""
        pass


class MQTTService(MessagingService):
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

    @override
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

    @override
    def disconnect(self):
        """Disconnect from the MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()
        self.logger.info("Disconnected from MQTT broker")

    @override
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

    @override
    def subscribe(self, topic: str, callback: Callable, qos: int = 1):
        """Subscribe to a topic with a callback"""
        self.topic_callbacks.setdefault(topic, []).append(callback)
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


class KafkaService(MessagingService):
    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        client_id: str = "digital_twin",
        group_id: str = "digital_twin_group",
    ) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.client_id = client_id
        self.group_id = group_id
        self.logger = get_logger(__name__)
        self.producer = None
        self.consumer = None
        self.consumer_thread = None
        self.topic_callbacks = {}
        self._running = False

    def connect(self) -> bool:
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                client_id=self.client_id,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            self.logger.info(f"Connected to Kafka at {self.bootstrap_servers}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to Kafka: {e}")
            return False

    def disconnect(self) -> None:
        self._running = False
        if self.producer:
            self.producer.close()

        if self.consumer:
            self.consumer.unsubscribe()
            self.consumer.close()
        if self.consumer_thread:
            self.consumer_thread.join()

        self.logger.info("Disconnected from Kafka")

    def publish(self, topic: str, payload: SensorData, **kwargs) -> bool:
        try:
            if not self.producer:
                self.logger.error("Not connected to Kafka")
                return False

            future = self.producer.send(topic, payload.to_dict())
            future.get(timeout=10)  # Wait for acknowledgment
            self.logger.debug(f"Published to {topic}: {payload}")
            return True
        except Exception as e:
            self.logger.error(f"Error publishing message: {e}")
            return False

    def subscribe(self, topic: str, callback: Callable, **kwargs) -> bool:
        try:
            # No new thread - just register the callback
            self.topic_callbacks.setdefault(topic, []).append(callback)

            if not self.consumer:
                self.consumer = KafkaConsumer(
                    bootstrap_servers=self.bootstrap_servers,
                    group_id=self.group_id,
                    auto_offset_reset="latest",
                    value_deserializer=lambda x: json.loads(x.decode("utf-8")),
                )
                self.consumer_thread = threading.Thread(target=self._consume_messages, daemon=True)
                self._running = True
                self.consumer_thread.start()

            # Subscribe to the new topic WARNING: It is not incremental, it will replace the previous topics
            self.consumer.subscribe(list(self.topic_callbacks.keys()))
            self.logger.info(f"Subscribed to {topic}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to subscribe to {topic}: {e}")
            return False

    def _consume_messages(self):
        """Single method to consume messages from all subscribed topics"""
        try:
            while self._running:
                if self.consumer:
                    records = self.consumer.poll(timeout_ms=1000)
                    for tp, messages in records.items():
                        topic = tp.topic
                        for message in messages:
                            try:
                                if not SensorData.validate_json(json.dumps(message.value)):
                                    self.logger.error(f"Received malformed data on {topic}")
                                    continue

                                # Execute callbacks for this topic
                                if topic in self.topic_callbacks:
                                    for callback in self.topic_callbacks.get(topic, []):
                                        sensor_data = SensorData.from_dict(message.value)
                                        callback(sensor_data)
                            except Exception as e:
                                self.logger.error(f"Error processing message: {e}")
                else:
                    time.sleep(1)  # No consumer yet, wait a bit
        except Exception as e:
            if self._running:
                self.logger.error(f"Error in consumer thread: {e}")
