"""Tests for the Socket.IO event naming contract.

The frontend subscribes to Socket.IO events named after Kafka processed topics
(`dt.sensors.processed.<short_name>`). These tests ensure the backend emits
payloads under that same event name.
"""

from dt.communication.dataclasses.processed_sensor_data import ProcessedSensorData, ValidationFlag
from dt.communication.topics import Topics
from dt.webapp import app as webapp_app
from dt.webapp import consumer


def test_forward_to_socketio_emits_on_processed_topic_name(monkeypatch):
    """Ensure emitted event name matches the processed topic string."""
    emitted = []

    def fake_emit(event_name, payload):
        emitted.append((event_name, payload))

    monkeypatch.setattr(webapp_app.socketio, "emit", fake_emit)

    with consumer.latest_by_topic_lock:
        consumer.latest_by_topic.clear()

    callback = consumer.forward_to_socketio(webapp_app.socketio, Topics.TEMPERATURE)

    reading = ProcessedSensorData(
        plant_id=1,
        sensor_id=2,
        timestamp=1735689600.0,
        value=22.5,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="corr-123",
        flags={ValidationFlag.VALID: True},
        dq_score=1.0,
        imputed=False,
    )

    callback(reading)

    assert emitted
    assert emitted[-1][0] == Topics.TEMPERATURE.processed
    with consumer.latest_by_topic_lock:
        assert Topics.TEMPERATURE.processed in consumer.latest_by_topic
