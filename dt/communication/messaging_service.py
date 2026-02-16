import json
import threading
import time
from abc import ABC, abstractmethod
from typing import Callable

from kafka import KafkaConsumer, KafkaProducer
from typing_extensions import override

from dt.communication.adapters import dump, load
from dt.communication.dataclasses import ProcessedSensorData, RawSensorData
from dt.communication.dataclasses.controller import ActionCommand
from dt.communication.dataclasses.alerts.alert_record import (
    AlertHistoryEvent,
    ExternalAlertEvent,
    SensorAlertEvent,
)
from dt.communication.topics import Topics
from dt.utils import get_logger


class MessagingService(ABC):
    """Abstract base class for messaging services.

    This class defines the interface for messaging services such as MQTT and
    Kafka, ensuring that they provide a consistent API for connecting,

    disconnecting, publishing, and subscribing to topics.
    """

    @abstractmethod
    def connect(self) -> bool:
        """Connect to the messaging service.

        Returns
        -------
        bool
            True if the connection is successful, False otherwise.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the messaging service"""
        pass

    @abstractmethod
    def publish(self, topic: str, payload, **kwargs) -> bool:
        """Publish a message to a topic.

        Parameters
        ----------
        topic : str
            The topic to publish the message to.
        payload : SensorData
            The data to be sent as the message payload.
        **kwargs
            Additional keyword arguments for the specific messaging service.

        Returns
        -------
        bool
            True if the message is published successfully, False otherwise.
        """
        pass

    @abstractmethod
    def subscribe(self, topic: str, callback: Callable, **kwargs) -> bool:
        """Subscribe to a topic with a callback function.

        Parameters
        ----------
        topic : str
            The topic to subscribe to.
        callback : Callable
            The function to be called when a message is received on the topic.
        **kwargs
            Additional keyword arguments for the specific messaging service.

        Returns
        -------
        bool
            True if the subscription is successful, False otherwise.
        """
        pass


class KafkaService(MessagingService):
    """A Kafka-based implementation of the MessagingService.

    This class provides a client for interacting with a Kafka cluster.

    Parameters
    ----------
    host : str, optional
        The host and port of the Kafka bootstrap server, by default "localhost:9092".
    client_id : str, optional
        The client ID to use for the Kafka connection, by default "digital_twin".
    group_id : str, optional
        The consumer group ID to use for subscriptions, by default "digital_twin_group".
    """

    def __init__(
        self,
        host: str = "localhost:9092",
        client_id: str = "digital_twin",
        group_id: str = "digital_twin_group",
    ) -> None:
        self.bootstrap_servers = host
        self.client_id = client_id
        self.group_id = group_id
        self.logger = get_logger(__name__)
        self.producer: KafkaProducer | None = None
        self.consumer: KafkaConsumer | None = None
        self.consumer_thread: threading.Thread | None = None
        self.topic_callbacks: dict[str, list[Callable]] = {}
        self._running = False

    @override
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

    @override
    def disconnect(self) -> None:
        self._running = False
        if self.producer:
            self.producer.close()

        if self.consumer:
            self.consumer.unsubscribe()
            self.consumer.close()
        if self.consumer_thread and self.consumer_thread.is_alive():
            self.consumer_thread.join()

        self.logger.info("Disconnected from Kafka")

    @override
    def publish(self, topic: str, payload, **kwargs) -> bool:
        try:
            if not self.producer:
                self.logger.error("Not connected to Kafka")
                return False

            future = self.producer.send(topic, dump("generic", payload))
            future.get(timeout=10)  # Wait for acknowledgment
            self.logger.debug(f"Published to {topic}: {payload}")
            return True
        except Exception as e:
            self.logger.error(f"Error publishing message: {e}")
            return False

    @override
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
                self._running = True
                self.consumer_thread = threading.Thread(target=self._consume_messages, daemon=True)
                self.consumer_thread.start()

            # Subscribe to the new topic WARNING: It is not incremental, it will replace the previous topics
            self.consumer.subscribe(list(self.topic_callbacks.keys()))
            self.logger.info(f"Subscribed to {topic}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to subscribe to {topic}: {e}")
            return False

    def _consume_messages(self):
        """Internal method to consume messages from all subscribed topics.

        This method runs in a background thread and polls for new messages,
        executing the appropriate callbacks when messages are received.
        """
        try:
            while self._running:
                if self.consumer:
                    records = self.consumer.poll(timeout_ms=1000)
                    for tp, messages in records.items():
                        topic = tp.topic
                        for message in messages:
                            try:
                                # Determine message type based on topic
                                if topic == Topics.ALERTS:
                                    # Deserialize as AlertHistoryEvent (with duck-typing for subclasses)
                                    raw_data = message.value
                                    # Duck-type to determine alert event subclass
                                    if "reading" in raw_data:
                                        data = load("generic", SensorAlertEvent, raw_data)
                                    elif "metadata" in raw_data:
                                        data = load("generic", ExternalAlertEvent, raw_data)
                                    else:
                                        data = load("generic", AlertHistoryEvent, raw_data)

                                elif "processed" in topic:
                                    # Deserialize as ProcessedSensorData
                                    data = load("generic", ProcessedSensorData, message.value)
                                elif topic == Topics.ACTIONS:
                                    # Deserialize as ActionCommand
                                    data = load("generic", ActionCommand, message.value)
                                else:
                                    # Deserialize as RawSensorData
                                    data = load("generic", RawSensorData, message.value)

                                # Execute callbacks for this topic
                                if topic in self.topic_callbacks:
                                    for callback in self.topic_callbacks.get(topic, []):
                                        callback(data)
                            except Exception as e:
                                self.logger.error(f"Error processing message: {e}")
                else:
                    time.sleep(1)  # No consumer yet, wait a bit
        except Exception as e:
            if self._running:
                self.logger.error(f"Error in consumer thread: {e}")