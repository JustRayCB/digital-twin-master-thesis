"""Messaging bridge consumer for the database service."""

import uuid

from dt.communication.dataclasses import CameraSnapshot, ProcessedSensorData
from dt.communication.dataclasses.alerts.alert_record import AlertHistoryEvent
from dt.communication.dataclasses.controller import ActionCommand
from dt.communication.dataclasses.analytics import Recommendation
from dt.communication.messaging_service import KafkaService, MessagingService
from dt.communication.topics import Topics
from dt.data.database import (AlertStorage, AnalyticsStorage, ControllerStorage,
                              ReadingsStorage, SnapshotStorage)
from dt.utils import get_logger

logger = get_logger(__name__)


def setup_bridge(
    config,
    readings_storage: ReadingsStorage,
    alert_storage: AlertStorage,
    analytics_storage: AnalyticsStorage,
    controller_storage: ControllerStorage,
    snapshot_storage: SnapshotStorage,
) -> MessagingService:
    """Set up the messaging bridge to the database.

    This function initializes a Kafka client, connects to the broker, and
    subscribes to all processed sensor data topics. Messages are forwarded
    to the provided storage backend.

    Parameters
    ----------
    config : Config
        Configuration object containing Kafka settings.
    readings_storage, alert_storage, analytics_storage, controller_storage, snapshot_storage
        Storage backends required to persist bridge messages.

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
        readings_storage.ingest_reading(payload)

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
        event_id = alert_storage.save_alert_event(event)
        logger.info(f"Persisted alert event with ID {event_id}")

    def persist_camera_snapshot(snapshot: CameraSnapshot):
        """Persist camera snapshots received on the camera processed topic.

        Parameters
        ----------
        snapshot : CameraSnapshot
            The camera snapshot payload received from the messaging service.
        """
        logger.info(
            f"Received camera snapshot: sensor_id={snapshot.sensor_id}, "
            f"timestamp={snapshot.timestamp}"
        )
        snapshot_storage.ingest_camera_snapshot(snapshot)

    def persist_action_execution(action: ActionCommand):
        """Persist action execution events received on the actions topic."""
        logger.info(
            f"Received action event: action_id={action.action_id}, "
            f"status={action.status}, correlation_id={action.correlation_id}"
        )
        controller_storage.log_action_execution(action)

    def persist_health_assessment(assessment):
        """Persist health assessments received from analytics."""
        logger.info(
            f"Received health assessment: plant_id={assessment.plant_id}, "
            f"correlation_id={assessment.correlation_id}"
        )
        analytics_storage.log_health_assessment(assessment)

    def persist_forecast_result(forecast):
        """Persist forecast results received from analytics."""
        logger.info(
            f"Received forecast result: plant_id={forecast.plant_id}, "
            f"metric={forecast.metric}, correlation_id={forecast.correlation_id}"
        )
        analytics_storage.log_forecast_result(forecast)

    def persist_recommendation(recommendation: Recommendation):
        """Persist recommendation events."""
        logger.info(
            f"Received recommendation: plant_id={recommendation.plant_id}, "
            f"correlation_id={recommendation.correlation_id}"
        )
        analytics_storage.log_recommendation(recommendation)

    unique_id = f"database_{uuid.uuid4().hex[:8]}"
    client: MessagingService = KafkaService(
        host=config.KAFKA_URL, client_id=unique_id, group_id="database_consumer_group"
    )
    if not client.connect():
        logger.error("Failed to connect to Messaging Service's broker")
        raise ConnectionError("Failed to connect to messaging broker")

    # Subscribe to all processed sensor topics
    for topic in Topics.list_sensor_topics():
        if topic in (Topics.CAMERA_IMAGE_TOP, Topics.CAMERA_IMAGE_SIDE):
            client.subscribe(topic.raw, persist_camera_snapshot)
            continue
        client.subscribe(topic.processed, forward_to_database)

    # Subscribe to alerts topic
    client.subscribe(Topics.ALERTS, persist_alert_event)
    client.subscribe(Topics.ACTIONS, persist_action_execution)
    client.subscribe(Topics.ANALYTICS_HEALTH, persist_health_assessment)
    client.subscribe(Topics.ANALYTICS_FORECAST, persist_forecast_result)
    client.subscribe(Topics.RECOMMENDATIONS_COMPLETED, persist_recommendation)

    logger.info("Messaging bridge setup complete")
    return client
