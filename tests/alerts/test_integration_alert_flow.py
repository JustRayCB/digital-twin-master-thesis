"""Integration test for end-to-end alert flow.

Tests the complete alert lifecycle from rule evaluation through acknowledgment,
using fake components to verify the alert engine behaves correctly end-to-end.
"""

import time
from unittest.mock import Mock

import pytest

from dt.alerts.config.alert_rule import (AlertCondition, AlertRule,
                                         ConditionType, EvaluationStage,
                                         SeverityLevel)
from dt.alerts.engine.evaluator import RuleEvaluator
from dt.alerts.engine.publisher import AlertPublisher
from dt.alerts.service import AlertEngineService
from dt.alerts.state.models import AlertLifecycleEvent
from dt.alerts.state.registry import AlertRegistry
from dt.communication import Topics
from dt.communication.dataclasses import ProcessedSensorData
from dt.communication.dataclasses.processed_sensor_data import ValidationFlag


@pytest.fixture
def threshold_rule():
    """Create a threshold-based alert rule."""
    condition = AlertCondition(
        type=ConditionType.THRESHOLD, params={"operator": ">", "threshold": 35.0}
    )
    return AlertRule(
        rule_id="temp_high",
        name="High Temperature Alert",
        description="Temperature exceeds {threshold}°C (actual: {value}°C)",
        severity=SeverityLevel.WARNING,
        evaluation_stage=EvaluationStage.PROCESSED,
        source="temperature",
        condition=condition,
        persistence_count=2,
        cooldown_seconds=300,
    )


@pytest.fixture
def dq_rule():
    """Create a DQ score-based alert rule."""
    condition = AlertCondition(type=ConditionType.DQ_SCORE, params={"threshold": 0.5})
    return AlertRule(
        rule_id="dq_low",
        name="Low Data Quality Alert",
        description="Data quality score {dq_score} below threshold {threshold}",
        severity=SeverityLevel.CRITICAL,
        evaluation_stage=EvaluationStage.PROCESSED,
        source="*",  # Apply to all sources
        condition=condition,
        persistence_count=3,
        cooldown_seconds=120,
    )


@pytest.fixture
def fake_publisher():
    """Create a fake publisher that captures published messages."""

    class FakePublisher:
        def __init__(self):
            self.published_events = []

        def publish(self, event, payload, actor=None):
            self.published_events.append(
                {"event": event, "payload": payload, "actor": actor}
            )
            return True

    return FakePublisher()


@pytest.fixture
def alert_service(threshold_rule, dq_rule, fake_publisher):
    """Create alert service with fake components."""
    # Create real registry and evaluator
    registry = AlertRegistry()
    evaluator = RuleEvaluator([threshold_rule, dq_rule])

    # Use mock Kafka service (not needed for this test)
    mock_kafka = Mock()

    # Create service with fake publisher
    service = AlertEngineService(
        kafka_service=mock_kafka,
        evaluator=evaluator,
        registry=registry,
        publisher=fake_publisher,
    )

    return service


def create_processed_reading(
    value: float, dq_score: float = 1.0, correlation_id: str = "test-corr-1"
) -> ProcessedSensorData:
    """Helper to create a processed sensor reading."""
    return ProcessedSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=time.time(),
        value=value,
        unit="Celsius",
        topic=Topics.TEMPERATURE,
        correlation_id=correlation_id,
        flags={ValidationFlag.VALID: True},
        dq_score=dq_score,
        imputed=False,
    )


def test_alert_flow_with_persistence_threshold(alert_service, fake_publisher):
    """Test that alerts are created only after reaching persistence threshold.

    Scenario:
    1. Send first high-temperature reading (persistence=2, so should be IGNORED)
    2. Send second high-temperature reading (should trigger CREATED)
    3. Verify publisher captured the CREATED event with correct alert details
    """
    # First reading exceeding threshold (38°C > 35°C)
    reading1 = create_processed_reading(value=38.0, correlation_id="corr-1")
    alert_service._on_message(reading1)

    # Should not publish yet (persistence_count=2)
    assert len(fake_publisher.published_events) == 0

    # Second reading exceeding threshold
    reading2 = create_processed_reading(value=39.0, correlation_id="corr-2")
    alert_service._on_message(reading2)

    # Should now publish CREATED event
    assert len(fake_publisher.published_events) == 1

    event_data = fake_publisher.published_events[0]
    assert event_data["event"] == AlertLifecycleEvent.CREATED
    assert event_data["payload"].alert_id == "temp_high:temperature"
    assert event_data["payload"].severity == SeverityLevel.WARNING
    assert "39.0" in event_data["payload"].message
    assert event_data["payload"].correlation_id == "corr-2"


def test_dq_alert_with_higher_persistence(alert_service, fake_publisher):
    """Test DQ alert requires 3 consecutive violations (higher persistence).

    Scenario:
    1. Send 2 low-DQ readings (should be IGNORED)
    2. Send 3rd low-DQ reading (should trigger CREATED)
    3. Verify publisher captured the CREATED event
    """
    # DQ rule has persistence_count=3 and applies to all sources (wildcard)
    reading1 = create_processed_reading(value=25.0, dq_score=0.3, correlation_id="dq-1")
    alert_service._on_message(reading1)
    assert len(fake_publisher.published_events) == 0

    reading2 = create_processed_reading(value=26.0, dq_score=0.4, correlation_id="dq-2")
    alert_service._on_message(reading2)
    assert len(fake_publisher.published_events) == 0

    # Third occurrence should create the alert
    reading3 = create_processed_reading(value=27.0, dq_score=0.2, correlation_id="dq-3")
    alert_service._on_message(reading3)

    # Should now publish CREATED event
    assert len(fake_publisher.published_events) == 1

    event_data = fake_publisher.published_events[0]
    assert event_data["event"] == AlertLifecycleEvent.CREATED
    assert event_data["payload"].alert_id == "dq_low:temperature"
    assert event_data["payload"].severity == SeverityLevel.CRITICAL
    assert "0.2" in event_data["payload"].message


def test_alert_updated_after_cooldown(alert_service, fake_publisher, threshold_rule):
    """Test that alert fires UPDATED event after cooldown expires.

    Scenario:
    1. Create alert (persistence=2)
    2. Send another high reading within cooldown (should be SUPPRESSED, no publish)
    3. Wait for cooldown to expire
    4. Send another high reading (should trigger UPDATED)
    5. Verify publisher captured both CREATED and UPDATED events
    """
    # Use short cooldown for testing
    threshold_rule.cooldown_seconds = 0.1

    # Create alert with 2 readings
    reading1 = create_processed_reading(value=38.0, correlation_id="corr-1")
    alert_service._on_message(reading1)

    reading2 = create_processed_reading(value=39.0, correlation_id="corr-2")
    alert_service._on_message(reading2)

    # Should have CREATED event
    assert len(fake_publisher.published_events) == 1
    assert fake_publisher.published_events[0]["event"] == AlertLifecycleEvent.CREATED

    # Immediate re-occurrence within cooldown (should be suppressed, not published)
    reading3 = create_processed_reading(value=40.0, correlation_id="corr-3")
    alert_service._on_message(reading3)

    # Still only one published event (SUPPRESSED events are not published)
    assert len(fake_publisher.published_events) == 1

    # Wait for cooldown to expire
    time.sleep(0.15)

    # Send another reading after cooldown
    reading4 = create_processed_reading(value=41.0, correlation_id="corr-4")
    alert_service._on_message(reading4)

    # Should now have both CREATED and UPDATED events
    assert len(fake_publisher.published_events) == 2
    assert fake_publisher.published_events[0]["event"] == AlertLifecycleEvent.CREATED
    assert fake_publisher.published_events[1]["event"] == AlertLifecycleEvent.UPDATED
    assert fake_publisher.published_events[1]["payload"].correlation_id == "corr-4"


def test_acknowledgment_publishes_lifecycle_event(alert_service, fake_publisher):
    """Test that acknowledging an alert publishes an ACKNOWLEDGED lifecycle event.

    Scenario:
    1. Create an alert (send 2 high-temp readings)
    2. Acknowledge the alert via registry
    3. Manually publish the acknowledgment event (simulating REST API behavior)
    4. Verify publisher captured both CREATED and ACKNOWLEDGED events
    """
    # Create alert
    reading1 = create_processed_reading(value=38.0, correlation_id="corr-1")
    alert_service._on_message(reading1)

    reading2 = create_processed_reading(value=39.0, correlation_id="corr-2")
    alert_service._on_message(reading2)

    # Should have CREATED event
    assert len(fake_publisher.published_events) == 1
    assert fake_publisher.published_events[0]["event"] == AlertLifecycleEvent.CREATED

    # Acknowledge the alert
    alert_id = "temp_high:temperature"
    success = alert_service.registry.acknowledge(alert_id, actor="test_operator")
    assert success is True

    # Simulate REST API publishing acknowledgment (this would be done by the API endpoint)
    alert_service.publisher.publish(
        AlertLifecycleEvent.ACKNOWLEDGED, alert_id, actor="test_operator"
    )

    # Should now have both CREATED and ACKNOWLEDGED events
    assert len(fake_publisher.published_events) == 2
    assert fake_publisher.published_events[1]["event"] == AlertLifecycleEvent.ACKNOWLEDGED
    assert fake_publisher.published_events[1]["payload"] == alert_id
    assert fake_publisher.published_events[1]["actor"] == "test_operator"


def test_multiple_rules_trigger_independently(alert_service, fake_publisher):
    """Test that multiple rules can trigger independently on the same payload.

    Scenario:
    1. Send readings with both high temperature AND low DQ score
    2. Verify both threshold and DQ alerts are created independently
    """
    # Send readings that violate both rules
    # Threshold rule: persistence=2, DQ rule: persistence=3
    reading1 = create_processed_reading(value=38.0, dq_score=0.3, correlation_id="multi-1")
    alert_service._on_message(reading1)
    assert len(fake_publisher.published_events) == 0  # Neither at persistence yet

    reading2 = create_processed_reading(value=39.0, dq_score=0.4, correlation_id="multi-2")
    alert_service._on_message(reading2)
    # Threshold alert should be created now (persistence=2)
    assert len(fake_publisher.published_events) == 1
    assert fake_publisher.published_events[0]["payload"].alert_id == "temp_high:temperature"

    reading3 = create_processed_reading(value=40.0, dq_score=0.2, correlation_id="multi-3")
    alert_service._on_message(reading3)
    # DQ alert should be created now (persistence=3)
    assert len(fake_publisher.published_events) == 2
    assert fake_publisher.published_events[1]["payload"].alert_id == "dq_low:temperature"

    # Both alerts should have been created independently
    alert_ids = {event["payload"].alert_id for event in fake_publisher.published_events}
    assert alert_ids == {"temp_high:temperature", "dq_low:temperature"}
