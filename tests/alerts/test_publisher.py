"""Tests for alert event publisher."""

import pytest

from dt.alerts.publisher import AlertPublisher
from dt.alerts.rules import SeverityLevel
from dt.communication.dataclasses import ProcessedSensorData
from dt.communication.dataclasses.alerts.alert_record import (
    AlertDefinition,
    AlertStatus,
    ExternalAlertEvent,
    SensorAlertEvent,
)
from dt.communication.dataclasses.alerts.alert_type import AlertType
from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.topics import Topics
from tests.alerts.conftest import collect_alert_events, poll_alert_event

pytestmark = [pytest.mark.requires_kafka, pytest.mark.requires_timescale]


@pytest.fixture
def sensor_alert_event(sample_sensor):
    """Create a sensor alert event backed by a registered sensor.

    Parameters
    ----------
    sample_sensor : SensorDescriptor
        Registered sensor descriptor from the test database.

    Returns
    -------
    SensorAlertEvent
        Sensor alert event tied to a persisted sensor.
    """
    reading = ProcessedSensorData(
        plant_id=sample_sensor.plant_id,
        sensor_id=sample_sensor.id,
        timestamp=1234567890.0,
        value=38.0,
        unit="°C",
        topic=Topics.TEMPERATURE,
        correlation_id="test-corr-123",
        flags={ValidationFlag.VALID: True},
        dq_score=1.0,
        imputed=False,
    )
    return SensorAlertEvent(
        alert_key="temp_high:temperature",
        plant_id=sample_sensor.plant_id,
        timestamp=1234567890.0,
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.WARNING,
        message="Temperature exceeds 35°C (actual: 38°C)",
        correlation_id="test-corr-123",
        reading=reading,
        threshold_op=">",
        threshold_value=35.0,
    )


@pytest.fixture
def alert_definition(sample_sensor):
    """Create a sensor alert definition backed by a registered sensor.

    Parameters
    ----------
    sample_sensor : SensorDescriptor
        Registered sensor descriptor from the test database.

    Returns
    -------
    AlertDefinition
        Alert definition tied to a persisted sensor.
    """
    return AlertDefinition(
        alert_key="temp_high:temperature",
        plant_id=sample_sensor.plant_id,
        sensor_id=sample_sensor.id,
        source="temperature",
        rule_id="temp_high",
        rule_name="Temp High",
        kind=AlertType.SENSOR,
        persistence_count=1,
        cooldown_seconds=300,
    )


def test_publish_created_event(publisher, alerts_consumer, sensor_alert_event, alert_definition):
    """Test publishing CREATED lifecycle event.

    Parameters
    ----------
    publisher : AlertPublisher
        Publisher instance under test.
    alerts_consumer : KafkaConsumer
        Kafka consumer subscribed to the alerts topic.
    sensor_alert_event : SensorAlertEvent
        Sample sensor alert event payload.
    alert_definition : AlertDefinition
        Sample alert definition for persistence.

    Returns
    -------
    None
        The assertions raise if publishing regresses.
    """
    publisher.publish(alert_definition, sensor_alert_event)

    alert_message = poll_alert_event(alerts_consumer)
    assert alert_message is not None
    assert alert_message.status == AlertStatus.ACTIVE
    assert alert_message.alert_key == sensor_alert_event.alert_key
    assert alert_message.plant_id == sensor_alert_event.plant_id
    # Verify it's a SensorAlertEvent with reading
    assert isinstance(alert_message, SensorAlertEvent)
    assert alert_message.reading.value == 38.0


def test_publish_updated_event(publisher, alerts_consumer, sensor_alert_event, alert_definition):
    """Test publishing UPDATED lifecycle event.

    Parameters
    ----------
    publisher : AlertPublisher
        Publisher instance under test.
    alerts_consumer : KafkaConsumer
        Kafka consumer subscribed to the alerts topic.
    sensor_alert_event : SensorAlertEvent
        Sample sensor alert event payload.
    alert_definition : AlertDefinition
        Sample alert definition for persistence.

    Returns
    -------
    None
        The assertions raise if publishing regresses.
    """
    publisher.publish(alert_definition, sensor_alert_event)

    alert_message = poll_alert_event(alerts_consumer)
    assert alert_message is not None

    # Verify event data is correct
    assert alert_message.status == AlertStatus.ACTIVE
    assert alert_message.alert_key == sensor_alert_event.alert_key


def test_publish_acknowledged_event(publisher, alerts_consumer, sample_sensor):
    """Test publishing ACKNOWLEDGED lifecycle event with alert and actor.

    Parameters
    ----------
    publisher : AlertPublisher
        Publisher instance under test.
    alerts_consumer : KafkaConsumer
        Kafka consumer subscribed to the alerts topic.
    sample_sensor : SensorDescriptor
        Registered sensor descriptor from the test database.

    Returns
    -------
    None
        The assertions raise if publishing regresses.
    """
    actor = "user@example.com"

    alert_event = SensorAlertEvent(
        alert_key="test_alert_123",
        plant_id=sample_sensor.plant_id,
        timestamp=1234567890.0,
        status=AlertStatus.ACKNOWLEDGED,
        severity=SeverityLevel.WARNING,
        message="Ack me",
        correlation_id="ack-corr",
        acknowledged_by=actor,
        reading=ProcessedSensorData(
            plant_id=sample_sensor.plant_id,
            sensor_id=sample_sensor.id,
            timestamp=1234567890.0,
            value=10.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="ack-corr",
            flags={},
            dq_score=1.0,
            imputed=False,
        ),
    )

    definition = AlertDefinition(
        alert_key=alert_event.alert_key,
        plant_id=alert_event.plant_id,
        sensor_id=alert_event.reading.sensor_id,
        source=alert_event.reading.topic.short_name,
        rule_id="test_alert_123",
        rule_name="Ack me",
        kind=AlertType.SENSOR,
        persistence_count=1,
        cooldown_seconds=300,
    )

    publisher.publish(definition, alert_event)

    alert_message = poll_alert_event(alerts_consumer)
    assert alert_message is not None
    assert alert_message.status == AlertStatus.ACKNOWLEDGED
    assert alert_message.alert_key == "test_alert_123"
    assert alert_message.acknowledged_by == actor
    assert alert_message.acknowledged_ts is not None


def test_publish_raises_when_definition_persist_fails(
    publisher, alerts_consumer, sample_sensor, alert_definition
):
    """Publisher should stop and raise when definition persistence fails.

    Parameters
    ----------
    publisher : AlertPublisher
        Publisher instance under test.
    alerts_consumer : KafkaConsumer
        Kafka consumer subscribed to the alerts topic.
    sample_sensor : SensorDescriptor
        Registered sensor descriptor from the test database.
    alert_definition : AlertDefinition
        Alert definition tied to a persisted sensor.

    Returns
    -------
    None
        The assertions raise if failure handling regresses.
    """
    invalid_definition = AlertDefinition(
        alert_key="bad_def:temperature",
        plant_id=sample_sensor.plant_id + 9999,
        sensor_id=None,
        source="external",
        rule_id=None,
        rule_name=None,
        kind=AlertType.EXTERNAL,
        persistence_count=1,
        cooldown_seconds=300,
    )
    alert_event = SensorAlertEvent(
        alert_key=invalid_definition.alert_key,
        plant_id=invalid_definition.plant_id,
        timestamp=1234567890.0,
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.WARNING,
        message="Invalid definition",
        correlation_id="bad-def-1",
        reading=ProcessedSensorData(
            plant_id=sample_sensor.plant_id,
            sensor_id=sample_sensor.id,
            timestamp=1234567890.0,
            value=10.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="bad-def-1",
            flags={},
            dq_score=1.0,
            imputed=False,
        ),
    )

    with pytest.raises(RuntimeError):
        publisher.publish(invalid_definition, alert_event)

    assert poll_alert_event(alerts_consumer, timeout_seconds=1.0) is None


def test_publish_cleared_event(publisher, alerts_consumer, sample_sensor):
    """Test publishing CLEARED lifecycle event with alert.

    Parameters
    ----------
    publisher : AlertPublisher
        Publisher instance under test.
    alerts_consumer : KafkaConsumer
        Kafka consumer subscribed to the alerts topic.
    sample_sensor : SensorDescriptor
        Registered sensor descriptor from the test database.

    Returns
    -------
    None
        The assertions raise if publishing regresses.
    """
    alert_event = SensorAlertEvent(
        alert_key="test_alert_456",
        plant_id=sample_sensor.plant_id,
        timestamp=1234567890.0,
        status=AlertStatus.CLEARED,
        severity=SeverityLevel.WARNING,
        message="Clear me",
        correlation_id="clear-corr",
        reading=ProcessedSensorData(
            plant_id=sample_sensor.plant_id,
            sensor_id=sample_sensor.id,
            timestamp=1234567890.0,
            value=10.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="clear-corr",
            flags={},
            dq_score=1.0,
            imputed=False,
        ),
    )

    definition = AlertDefinition(
        alert_key=alert_event.alert_key,
        plant_id=alert_event.plant_id,
        sensor_id=alert_event.reading.sensor_id,
        source=alert_event.reading.topic.short_name,
        rule_id="test_alert_456",
        rule_name="Clear me",
        kind=AlertType.SENSOR,
        persistence_count=1,
        cooldown_seconds=300,
    )

    publisher.publish(definition, alert_event)

    alert_message = poll_alert_event(alerts_consumer)
    assert alert_message is not None

    # Verify AlertMessage structure
    assert alert_message.status == AlertStatus.CLEARED
    assert alert_message.alert_key == "test_alert_456"
    assert alert_message.cleared_ts is not None


def test_publish_multiple_events(publisher, alerts_consumer, sensor_alert_event, alert_definition):
    """Test publishing multiple events in sequence.

    Parameters
    ----------
    publisher : AlertPublisher
        Publisher instance under test.
    alerts_consumer : KafkaConsumer
        Kafka consumer subscribed to the alerts topic.
    sensor_alert_event : SensorAlertEvent
        Sample sensor alert event payload.
    alert_definition : AlertDefinition
        Sample alert definition for persistence.

    Returns
    -------
    None
        The assertions raise if publishing regresses.
    """
    # Create alert
    publisher.publish(alert_definition, sensor_alert_event)

    # Update alert
    publisher.publish(alert_definition, sensor_alert_event)

    # Acknowledge alert
    sensor_alert_event.status = AlertStatus.ACKNOWLEDGED
    sensor_alert_event.acknowledged_by = "dummy_user"
    publisher.publish(alert_definition, sensor_alert_event)

    events = collect_alert_events(alerts_consumer, count=3, timeout_seconds=5.0)
    assert len(events) == 3


def test_publish_with_external_submission(publisher, alerts_consumer, sample_plant_id):
    """Test publishing alert from external submission (no rule_name).

    Parameters
    ----------
    publisher : AlertPublisher
        Publisher instance under test.
    alerts_consumer : KafkaConsumer
        Kafka consumer subscribed to the alerts topic.
    sample_plant_id : int
        Plant identifier from the test database.

    Returns
    -------
    None
        The assertions raise if publishing regresses.
    """
    external_candidate = ExternalAlertEvent(
        alert_key="manual_alert_001",
        plant_id=sample_plant_id,
        timestamp=1234567890.0,
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.CRITICAL,
        message="Manual alert submitted by user",
        correlation_id="ext-corr-789",
        metadata={"submission_type": "external", "timestamp": "1234567890.0"},
    )

    definition = AlertDefinition(
        alert_key="manual_alert_001",
        plant_id=sample_plant_id,
        sensor_id=None,
        source="external",
        rule_id=None,
        rule_name=None,
        kind=AlertType.EXTERNAL,
        persistence_count=1,
        cooldown_seconds=300,
    )

    publisher.publish(definition, external_candidate)

    alert_message = poll_alert_event(alerts_consumer)
    assert alert_message is not None

    # Verify event data preserves all context
    assert alert_message.alert_key == "manual_alert_001"
    assert alert_message.severity == SeverityLevel.CRITICAL
    # Verify it's an ExternalAlertEvent with metadata
    assert isinstance(alert_message, ExternalAlertEvent)
    assert alert_message.metadata["submission_type"] == "external"


def test_publish_preserves_correlation_id(
    publisher, alerts_consumer, sensor_alert_event, alert_definition
):
    """Test that correlation ID is preserved in published events.

    Parameters
    ----------
    publisher : AlertPublisher
        Publisher instance under test.
    alerts_consumer : KafkaConsumer
        Kafka consumer subscribed to the alerts topic.
    sensor_alert_event : SensorAlertEvent
        Sample sensor alert event payload.
    alert_definition : AlertDefinition
        Sample alert definition for persistence.

    Returns
    -------
    None
        The assertions raise if correlation IDs regress.
    """
    publisher.publish(alert_definition, sensor_alert_event)

    alert_message = poll_alert_event(alerts_consumer)
    assert alert_message is not None

    # Verify correlation_id is preserved in the alert details
    assert alert_message.correlation_id == sensor_alert_event.correlation_id
