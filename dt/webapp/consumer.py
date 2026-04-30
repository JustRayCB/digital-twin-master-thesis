"""Messaging bridge consumer for the webapp service."""

import uuid
from datetime import datetime
from threading import Lock

from flask_socketio import SocketIO

from dt.communication.adapters import dump
from dt.communication.dataclasses import CameraSnapshot, ProcessedSensorData
from dt.communication.dataclasses.alerts.alert_record import (
    AlertHistoryEvent, AlertStatus)
from dt.communication.dataclasses.analytics import (ForecastResult,
                                                    HealthAssessment,
                                                    Recommendation)
from dt.communication.dataclasses.queries import ActiveAlertsQuery
from dt.communication.db_client import DatabaseApiClient
from dt.communication.messaging_service import KafkaService, MessagingService
from dt.communication.topics import Topics
from dt.utils import Config, get_logger

logger = get_logger(__name__)

latest_by_topic: dict[str, dict] = {}
latest_by_topic_lock = Lock()

active_alerts_by_key: dict[str, dict] = {}
active_alerts_lock = Lock()

connection_status = False


def alert_cache_key(alert_key: str, plant_id: int) -> str:
    return f"{int(plant_id)}:{alert_key}"


def shape_processed_reading_payload(reading: ProcessedSensorData) -> dict:
    """Convert a processed reading into the Socket.IO payload shape (JS timestamps in ms)."""
    payload = dump("web", reading)
    payload.pop("topic", None)
    return payload


def shape_camera_snapshot_payload(snapshot: CameraSnapshot) -> dict:
    """Convert a camera snapshot into the Socket.IO payload shape (JS timestamps in ms)."""
    payload = dump("web", snapshot)
    payload.pop("topic", None)
    return payload


def shape_recommendation_payload(recommendation: Recommendation) -> dict:
    """Convert a recommendation event into the Socket.IO payload shape."""
    return dump("web", recommendation)


def shape_analytics_payload(payload: HealthAssessment | ForecastResult) -> dict:
    """Convert an analytics event into the Socket.IO payload shape."""
    return dump("web", payload)


def update_latest_payload_cache(cache: dict[str, dict], topic: str, payload: dict) -> None:
    """Store the latest payload for a given topic."""
    cache[topic] = payload


def shape_alert_event_payload(event: AlertHistoryEvent) -> dict:
    """Convert an alert event into the Socket.IO payload shape (JS timestamps in ms)."""
    payload = dump("web", event)
    payload["alert_id"] = alert_cache_key(event.alert_key, event.plant_id)
    return payload


def apply_alert_event_to_cache(
    cache: dict[str, dict], event: AlertHistoryEvent
) -> list[tuple[str, dict | str]]:
    """Update the active alerts cache and return Socket.IO events to emit."""
    cache_key = alert_cache_key(event.alert_key, event.plant_id)
    if event.status != AlertStatus.CLEARED:
        payload = shape_alert_event_payload(event)
        cache[cache_key] = payload
        return [("alerts_update", payload)]

    cache.pop(cache_key, None)
    return [("alerts_remove", cache_key)]


def forward_to_socketio(socketio: SocketIO, topic: Topics):
    """Create a callback function to forward processed Kafka messages to SocketIO.

    This factory function returns a callback that can be used with the Kafka
    consumer. The returned callback takes a ProcessedSensorData payload and emits
    the full processed payload shape to the SocketIO event matching the Kafka processed topic.

    Parameters
    ----------
    topic : Topics
        The topic for which the callback is being created.

    Returns
    -------
    Callable[[SensorData], None]
        The callback function.
    """
    socketio_topic = topic.processed

    def callback(payload: ProcessedSensorData):
        date = datetime.fromtimestamp(payload.timestamp)
        logger.info(
            f"Received message for {topic.processed} at {date}: {payload.value} {payload.unit}"
        )
        shaped = shape_processed_reading_payload(payload)
        with latest_by_topic_lock:
            update_latest_payload_cache(latest_by_topic, socketio_topic, shaped)
        socketio.emit(socketio_topic, shaped)

    return callback


def forward_camera_snapshot_to_socketio(socketio: SocketIO, topic: Topics):
    """Create a callback that forwards camera snapshots to Socket.IO."""
    socketio_topic = topic.raw

    def callback(snapshot: CameraSnapshot):
        shaped = shape_camera_snapshot_payload(snapshot)
        with latest_by_topic_lock:
            update_latest_payload_cache(latest_by_topic, socketio_topic, shaped)
        socketio.emit(socketio_topic, shaped)

    return callback


def forward_analytics_to_socketio(socketio: SocketIO, topic: Topics):
    """Create a callback that forwards analytics payloads to Socket.IO."""
    socketio_topic = topic.value

    def callback(payload: HealthAssessment | ForecastResult):
        shaped = shape_analytics_payload(payload)
        with latest_by_topic_lock:
            update_latest_payload_cache(latest_by_topic, socketio_topic, shaped)
        socketio.emit(socketio_topic, shaped)

    return callback


def setup_bridge(db_client: DatabaseApiClient, socketio: SocketIO) -> MessagingService:
    """Set up the messaging bridge from Kafka to SocketIO.

    This function initializes a Kafka client, connects to the broker, and
    subscribes to all processed sensor data topics. For each topic, it sets
    up a callback using `forward_to_socketio` to relay the messages to the
    web clients.

    Returns
    -------
    MessagingService
        The initialized and connected messaging service client.
    """
    global connection_status
    unique_id = f"webapp_{uuid.uuid4().hex[:8]}"
    msg_client: MessagingService = KafkaService(
        host=Config.KAFKA_URL, client_id=unique_id, group_id="webapp_consumer_group"
    )
    if not msg_client.connect():
        logger.error("Failed to connect to Messaging Service's broker")
        # We don't raise here to allow the app to start even if Kafka is down
        # (The UI will just show disconnected)
        return msg_client

    connection_status = True

    try:
        active_alerts = db_client.get_active_alerts(ActiveAlertsQuery())
        with active_alerts_lock:
            for event in active_alerts:
                payload = shape_alert_event_payload(event)
                key = alert_cache_key(event.alert_key, event.plant_id)
                active_alerts_by_key[key] = payload
    except Exception as exc:
        logger.error(f"Failed to seed active alerts: {exc}")

    def forward_alert_event(event: AlertHistoryEvent) -> None:
        with active_alerts_lock:
            emitted = apply_alert_event_to_cache(active_alerts_by_key, event)
        for event_name, payload in emitted:
            socketio.emit(event_name, payload)

    def forward_recommendation_submitted(recommendation: Recommendation) -> None:
        socketio.emit("recommendations_submitted", shape_recommendation_payload(recommendation))

    def forward_recommendation_completed(recommendation: Recommendation) -> None:
        socketio.emit("recommendations_completed", shape_recommendation_payload(recommendation))

    def forward_action_event(action) -> None:
        socketio.emit(Topics.ACTIONS.value, dump("web", action))

    msg_client.subscribe(Topics.ALERTS, forward_alert_event)
    msg_client.subscribe(Topics.RECOMMENDATIONS_SUBMITTED, forward_recommendation_submitted)
    msg_client.subscribe(Topics.RECOMMENDATIONS_COMPLETED, forward_recommendation_completed)
    msg_client.subscribe(Topics.ACTIONS, forward_action_event)
    msg_client.subscribe(
        Topics.ANALYTICS_HEALTH, forward_analytics_to_socketio(socketio, Topics.ANALYTICS_HEALTH)
    )
    msg_client.subscribe(
        Topics.ANALYTICS_FORECAST,
        forward_analytics_to_socketio(socketio, Topics.ANALYTICS_FORECAST),
    )

    try:
        latest_snapshot = db_client.get_latest_camera_snapshot(plant_id=1)
        if latest_snapshot is not None:
            with latest_by_topic_lock:
                # Assuming the latest snapshot was from TOP
                update_latest_payload_cache(
                    latest_by_topic,
                    Topics.CAMERA_IMAGE_TOP.raw,
                    shape_camera_snapshot_payload(latest_snapshot),
                )
    except Exception as exc:
        logger.error(f"Failed to seed camera snapshot: {exc}")

    for topic in Topics.list_sensor_topics():
        if topic in (Topics.CAMERA_IMAGE_TOP, Topics.CAMERA_IMAGE_SIDE):
            msg_client.subscribe(topic.raw, forward_camera_snapshot_to_socketio(socketio, topic))
            continue
        msg_client.subscribe(topic.processed, forward_to_socketio(socketio, topic))

    return msg_client
