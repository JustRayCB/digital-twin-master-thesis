"""Messaging bridge consumer for the database service."""

import uuid

from dt.communication.messaging_service import MessagingService
from dt.communication.topics import Topics
from dt.communication.dataclasses import ProcessedSensorData
from dt.communication.dataclasses.alerts.alert_record import AlertHistoryEvent
from dt.communication.messaging_service import KafkaService
from dt.data.database.storage import Storage
from dt.utils import get_logger

logger = get_logger(__name__)


def setup_bridge(config, storage: Storage) -> MessagingService:
    """Set up the messaging bridge to the database.

    This function initializes a Kafka client, connects to the broker, and
    subscribes to all processed sensor data topics. Messages are forwarded
    to the provided storage backend.

    Parameters
    ----------
    config : Config
        Configuration object containing Kafka settings.
    storage : Storage
        Storage backend to persist messages to.

    Returns
    -------
    MessagingService
        The initialized and connected messaging service client.

    Raises
    ------
    ConnectionError
        If connection to Kafka broker fails.
    """
    logger.info("Setting up messaging bridge")

    def forward_to_database(payload: ProcessedSensorData):
        """Callback function for the messaging service.

        This function is called by the Kafka consumer whenever a message is
        received on a subscribed processed sensor topic. It persists the
        processed measurement into the TimescaleDB hypertable.

        Parameters
        ----------
        payload : ProcessedSensorData
            The processed sensor data received from the messaging service.
        """
        logger.info(
            f"Received processed measurement: sensor_id={payload.sensor_id}, "
            f"value={payload.value}, timestamp={payload.timestamp}"
        )
        storage.ingest_reading(payload)

    def persist_alert_event(event: AlertHistoryEvent):
        """Callback function for alert events from the messaging service.

        This function is called by the Kafka consumer whenever an alert event is
        received on the dt.alerts topic. It persists the alert event to the database
        for audit trail and history tracking.

        Parameters
        ----------
        event : AlertHistoryEvent
            The alert history event received from the messaging service.
        """
        logger.info(
            f"Received alert event: alert_key={event.alert_key}, "
            f"status={event.status}, timestamp={event.timestamp}"
        )

        # Save the alert history event
        event_id = storage.save_alert_event(event)
        logger.info(f"Persisted alert event with ID {event_id}")

    unique_id = f"database_{uuid.uuid4().hex[:8]}"
    client: MessagingService = KafkaService(
        host=config.KAFKA_URL, client_id=unique_id, group_id="database_consumer_group"
    )
    if not client.connect():
        logger.error("Failed to connect to Messaging Service's broker")
        raise ConnectionError("Failed to connect to messaging broker")

    # Subscribe to all processed sensor topics
    for topic in Topics.list_sensor_topics():
        client.subscribe(topic.processed, forward_to_database)

    # Subscribe to alerts topic
    client.subscribe(Topics.ALERTS, persist_alert_event)

    logger.info("Messaging bridge setup complete")
    return client
