"""Integration tests for end-to-end alert flow."""

import time

import pytest

from dt.alerts.evaluator import RuleEvaluator
from dt.alerts.registry import AlertRegistry
from dt.alerts.rules import AlertCondition, AlertRule, ConditionType, EvaluationStage, SeverityLevel
from dt.communication.dataclasses.alerts.alert_record import (
    AlertDefinition,
    AlertHistoryEvent,
    AlertStatus,
    SensorAlertEvent,
)
from dt.communication.dataclasses.alerts.alert_type import AlertType
from dt.communication.topics import Topics
from tests.alerts.conftest import build_processed_reading, poll_alert_event, running_alert_service

pytestmark = [pytest.mark.requires_kafka, pytest.mark.requires_timescale]


@pytest.fixture
def alert_service(threshold_rule, dq_rule, publisher, consumer_service):
    """Create alert service with Kafka-backed publisher.

    Parameters
    ----------
    threshold_rule : AlertRule
        Threshold rule used by the evaluator.
    dq_rule : AlertRule
        DQ score rule used by the evaluator.
    Returns
    -------
    AlertEngineService
        Alert engine service for integration tests.
    """
    # Create real registry and evaluator
    registry = AlertRegistry()
    evaluator = RuleEvaluator([threshold_rule, dq_rule])
    with running_alert_service(consumer_service, evaluator, registry, publisher) as service:
        yield service


def test_alert_flow_with_persistence_threshold(
    alert_service, alerts_consumer, processed_publisher, sample_sensor
):
    """Test that alerts are created only after reaching persistence threshold.

    Parameters
    ----------
    alert_service : AlertEngineService
        Service under test.
    alerts_consumer : KafkaConsumer
        Kafka consumer subscribed to the alerts topic.
    processed_publisher : KafkaService
        Kafka service used to publish processed readings.
    sample_sensor : SensorDescriptor
        Sensor descriptor providing plant and sensor IDs.
    Returns
    -------
    None
        The assertions raise if persistence handling regresses.
    """
    # First reading exceeding threshold (38°C > 35°C)
    reading1 = build_processed_reading(sample_sensor, value=38.0, correlation_id="corr-1")
    assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading1)

    # Should not publish yet (persistence_count=2)
    assert poll_alert_event(alerts_consumer, timeout_seconds=2.0) is None

    # Second reading exceeding threshold
    reading2 = build_processed_reading(sample_sensor, value=39.0, correlation_id="corr-2")
    assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading2)

    payload = poll_alert_event(alerts_consumer, timeout_seconds=10.0)
    assert payload is not None
    assert type(payload) is SensorAlertEvent
    assert payload.status == AlertStatus.ACTIVE
    assert payload.alert_key == "temp_high:temperature"
    assert payload.severity == SeverityLevel.WARNING
    assert "39.0" in payload.message
    assert payload.correlation_id == "corr-2"
    assert payload.reading.value == reading2.value


def test_dq_alert_with_higher_persistence(
    alert_service, alerts_consumer, processed_publisher, sample_sensor
):
    """Test DQ alert requires 3 consecutive violations (higher persistence).

    Parameters
    ----------
    alert_service : AlertEngineService
        Service under test.
    alerts_consumer : KafkaConsumer
        Kafka consumer subscribed to the alerts topic.
    processed_publisher : KafkaService
        Kafka service used to publish processed readings.
    sample_sensor : SensorDescriptor
        Sensor descriptor providing plant and sensor IDs.
    Returns
    -------
    None
        The assertions raise if persistence handling regresses.
    """
    # DQ rule has persistence_count=3 and applies to all sources (wildcard)
    reading1 = build_processed_reading(sample_sensor, value=25.0, dq_score=0.3, correlation_id="dq-1")
    assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading1)
    assert poll_alert_event(alerts_consumer, timeout_seconds=2.0) is None

    reading2 = build_processed_reading(sample_sensor, value=26.0, dq_score=0.4, correlation_id="dq-2")
    assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading2)
    assert poll_alert_event(alerts_consumer, timeout_seconds=2.0) is None

    # Third occurrence should create the alert
    reading3 = build_processed_reading(sample_sensor, value=27.0, dq_score=0.2, correlation_id="dq-3")
    assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading3)

    payload = poll_alert_event(alerts_consumer, timeout_seconds=10.0)
    assert payload is not None
    assert type(payload) is SensorAlertEvent
    assert payload.status == AlertStatus.ACTIVE
    assert payload.alert_key == "dq_low:temperature"
    assert payload.severity == SeverityLevel.CRITICAL
    assert "0.2" in payload.message
    assert payload.reading.dq_score == 0.2


def test_alert_updated_after_cooldown(
    alert_service,
    alerts_consumer,
    processed_publisher,
    threshold_rule,
    sample_sensor,
):
    """Test that alert fires UPDATED event after cooldown expires.

    Parameters
    ----------
    alert_service : AlertEngineService
        Service under test.
    alerts_consumer : KafkaConsumer
        Kafka consumer subscribed to the alerts topic.
    processed_publisher : KafkaService
        Kafka service used to publish processed readings.
    threshold_rule : AlertRule
        Rule defining the cooldown behavior.
    sample_sensor : SensorDescriptor
        Sensor descriptor providing plant and sensor IDs.
    Returns
    -------
    None
        The assertions raise if cooldown handling regresses.
    """
    # Use short cooldown for testing
    threshold_rule.cooldown_seconds = 0.1

    # Create alert with 2 readings
    reading1 = build_processed_reading(sample_sensor, value=38.0, correlation_id="corr-1")
    assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading1)

    reading2 = build_processed_reading(sample_sensor, value=39.0, correlation_id="corr-2")
    assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading2)

    created_payload = poll_alert_event(alerts_consumer, timeout_seconds=10.0)
    assert created_payload is not None
    assert created_payload.status == AlertStatus.ACTIVE

    # Immediate re-occurrence within cooldown (should be ignored, not published)
    reading3 = build_processed_reading(sample_sensor, value=40.0, correlation_id="corr-3")
    assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading3)

    assert poll_alert_event(alerts_consumer, timeout_seconds=2.0) is None

    # Wait for cooldown to expire
    time.sleep(0.15)

    # Send another reading after cooldown
    reading4 = build_processed_reading(sample_sensor, value=41.0, correlation_id="corr-4")
    assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading4)

    updated_payload = poll_alert_event(alerts_consumer, timeout_seconds=10.0)
    assert updated_payload is not None
    assert updated_payload.status == AlertStatus.ACTIVE
    assert updated_payload.correlation_id == "corr-4"


def test_acknowledgment_publishes_lifecycle_event(
    alert_service,
    alerts_consumer,
    processed_publisher,
    sample_sensor,
):
    """Test that acknowledging an alert publishes an ACKNOWLEDGED lifecycle event.

    Parameters
    ----------
    alert_service : AlertEngineService
        Service under test.
    alerts_consumer : KafkaConsumer
        Kafka consumer subscribed to the alerts topic.
    processed_publisher : KafkaService
        Kafka service used to publish processed readings.
    sample_sensor : SensorDescriptor
        Sensor descriptor providing plant and sensor IDs.
    Returns
    -------
    None
        The assertions raise if lifecycle publishing regresses.
    """
    # Create alert
    reading1 = build_processed_reading(sample_sensor, value=38.0, correlation_id="corr-1")
    assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading1)

    reading2 = build_processed_reading(sample_sensor, value=39.0, correlation_id="corr-2")
    assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading2)

    created_payload = poll_alert_event(alerts_consumer, timeout_seconds=10.0)
    assert created_payload is not None
    assert created_payload.status == AlertStatus.ACTIVE

    # Acknowledge the alert
    alert_key = "temp_high:temperature"
    success = alert_service.registry.acknowledge(alert_key, actor="test_operator")
    assert success is True

    # Simulate REST API publishing acknowledgment (this would be done by the API endpoint)
    alert_state = alert_service.registry.get_alert_state(alert_key)
    alert_event = AlertHistoryEvent(
        alert_key=alert_key,
        plant_id=alert_state.plant_id if alert_state else 0,
        timestamp=time.time(),
        status=AlertStatus.ACKNOWLEDGED,
        severity=alert_state.severity if alert_state else SeverityLevel.WARNING,
        message=alert_state.message if alert_state else "",
        correlation_id=alert_state.correlation_id if alert_state else "",
        acknowledged_by="test_operator",
    )

    definition = AlertDefinition(
        alert_key=alert_key,
        plant_id=alert_state.plant_id if alert_state else 0,
        sensor_id=None,
        source=alert_state.source if alert_state else "external",
        rule_id=alert_state.rule_id if alert_state else None,
        rule_name=alert_state.rule_id if alert_state else None,
        kind=(
            AlertType.EXTERNAL
            if (alert_state and alert_state.rule_id is None)
            else AlertType.SENSOR
        ),
        persistence_count=1,
        cooldown_seconds=300,
    )

    alert_service.publisher.publish(definition, alert_event)

    ack_payload = poll_alert_event(alerts_consumer, timeout_seconds=10.0)
    assert ack_payload is not None
    assert ack_payload.status == AlertStatus.ACKNOWLEDGED
    assert ack_payload.alert_key == alert_key
    assert ack_payload.acknowledged_by == "test_operator"
    assert ack_payload.plant_id == alert_state.plant_id
    assert ack_payload.correlation_id == alert_state.correlation_id


def test_multiple_rules_trigger_independently(
    alert_service,
    alerts_consumer,
    processed_publisher,
    sample_sensor,
):
    """Test that multiple rules can trigger independently on the same payload.

    Parameters
    ----------
    alert_service : AlertEngineService
        Service under test.
    alerts_consumer : KafkaConsumer
        Kafka consumer subscribed to the alerts topic.
    processed_publisher : KafkaService
        Kafka service used to publish processed readings.
    sample_sensor : SensorDescriptor
        Sensor descriptor providing plant and sensor IDs.
    Returns
    -------
    None
        The assertions raise if multi-rule handling regresses.
    """
    # Send readings that violate both rules
    # Threshold rule: persistence=2, DQ rule: persistence=3
    reading1 = build_processed_reading(sample_sensor, value=38.0, dq_score=0.3, correlation_id="multi-1")
    assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading1)
    assert poll_alert_event(alerts_consumer, timeout_seconds=2.0) is None

    reading2 = build_processed_reading(sample_sensor, value=39.0, dq_score=0.4, correlation_id="multi-2")
    assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading2)
    # Threshold alert should be created now (persistence=2)
    first_payload = poll_alert_event(alerts_consumer, timeout_seconds=10.0)
    assert first_payload is not None
    assert first_payload.alert_key == "temp_high:temperature"

    reading3 = build_processed_reading(sample_sensor, value=40.0, dq_score=0.2, correlation_id="multi-3")
    assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading3)
    # DQ alert should be created now (persistence=3)
    second_payload = poll_alert_event(alerts_consumer, timeout_seconds=10.0)
    assert second_payload is not None
    assert second_payload.alert_key == "dq_low:temperature"

    # Both alerts should have been created independently
    assert {first_payload.alert_key, second_payload.alert_key} == {
        "temp_high:temperature",
        "dq_low:temperature",
    }
