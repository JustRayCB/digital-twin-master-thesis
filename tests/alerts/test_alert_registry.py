"""Tests for alert registry state management."""

import time

import pytest

from dt.analytics.alerts.registry import AlertRegistry
from dt.analytics.alerts.rules import SeverityLevel
from dt.communication.dataclasses import ProcessedSensorData
from dt.communication.dataclasses.alerts.alert_record import (
    AlertStatus,
    ExternalAlertEvent,
    SensorAlertEvent,
)
from dt.communication.topics import Topics


def test_first_occurrence_below_persistence_is_ignored(registry, sample_sensor_alert_event):
    """Test that first occurrence below persistence threshold is ignored.

    Parameters
    ----------
    registry : AlertRegistry
        Registry instance under test.
    sample_sensor_alert_event : SensorAlertEvent
        Sample alert event to register.

    Returns
    -------
    None
        The assertions raise if persistence handling regresses.
    """
    event = registry.register(sample_sensor_alert_event, persistence_count=3, cooldown_seconds=300)

    assert event == AlertStatus.IGNORED
    # Alert should be tracked but not considered active yet
    assert sample_sensor_alert_event.alert_key in registry._states


def test_persistence_threshold_creates_alert(registry, sample_sensor_alert_event):
    """Test that reaching persistence threshold creates alert.

    Parameters
    ----------
    registry : AlertRegistry
        Registry instance under test.
    sample_sensor_alert_event : SensorAlertEvent
        Sample alert event to register.

    Returns
    -------
    None
        The assertions raise if persistence handling regresses.
    """
    # First two occurrences should be ignored
    event1 = registry.register(sample_sensor_alert_event, persistence_count=3, cooldown_seconds=300)
    assert event1 == AlertStatus.IGNORED

    event2 = registry.register(sample_sensor_alert_event, persistence_count=3, cooldown_seconds=300)
    assert event2 == AlertStatus.IGNORED

    # Third occurrence should create the alert
    event3 = registry.register(sample_sensor_alert_event, persistence_count=3, cooldown_seconds=300)
    assert event3 == AlertStatus.ACTIVE

    # Verify alert state
    state = registry._states[sample_sensor_alert_event.alert_key]
    assert state.occurrences == 3
    assert not state.acknowledged


def test_persistence_count_of_one_creates_immediately(registry, sample_sensor_alert_event):
    """Test that persistence_count=1 creates alert on first occurrence.

    Parameters
    ----------
    registry : AlertRegistry
        Registry instance under test.
    sample_sensor_alert_event : SensorAlertEvent
        Sample alert event to register.

    Returns
    -------
    None
        The assertions raise if persistence handling regresses.
    """
    event = registry.register(sample_sensor_alert_event, persistence_count=1, cooldown_seconds=300)

    assert event == AlertStatus.ACTIVE
    state = registry._states[sample_sensor_alert_event.alert_key]
    assert state.occurrences == 1


def test_alert_within_cooldown_is_ignored(registry, sample_sensor_alert_event):
    """Test that alerts within cooldown period are ignored.

    Parameters
    ----------
    registry : AlertRegistry
        Registry instance under test.
    sample_sensor_alert_event : SensorAlertEvent
        Sample alert event to register.

    Returns
    -------
    None
        The assertions raise if cooldown handling regresses.
    """
    # Create alert (persistence=1 for simplicity)
    event1 = registry.register(sample_sensor_alert_event, persistence_count=1, cooldown_seconds=300)
    assert event1 == AlertStatus.ACTIVE

    # Immediate re-occurrence should be ignored
    event2 = registry.register(sample_sensor_alert_event, persistence_count=1, cooldown_seconds=300)
    assert event2 == AlertStatus.IGNORED


def test_alert_after_cooldown_is_updated(registry, sample_sensor_alert_event):
    """Test that alerts after cooldown period are emitted as active again.

    Parameters
    ----------
    registry : AlertRegistry
        Registry instance under test.
    sample_sensor_alert_event : SensorAlertEvent
        Sample alert event to register.

    Returns
    -------
    None
        The assertions raise if cooldown handling regresses.
    """
    # Use very short cooldown for testing
    cooldown_seconds = 0.1

    # Create alert
    event1 = registry.register(
        sample_sensor_alert_event, persistence_count=1, cooldown_seconds=cooldown_seconds
    )
    assert event1 == AlertStatus.ACTIVE

    # Wait for cooldown to expire
    time.sleep(cooldown_seconds + 0.05)

    # Next occurrence should be allowed
    event2 = registry.register(
        sample_sensor_alert_event, persistence_count=1, cooldown_seconds=cooldown_seconds
    )
    assert event2 == AlertStatus.ACTIVE

    # Verify state was updated
    state = registry._states[sample_sensor_alert_event.alert_key]
    assert state.occurrences == 2


def test_acknowledge_sets_flag_and_returns_true(registry, sample_sensor_alert_event):
    """Test that acknowledging an alert sets the flag.

    Parameters
    ----------
    registry : AlertRegistry
        Registry instance under test.
    sample_sensor_alert_event : SensorAlertEvent
        Sample alert event to register.

    Returns
    -------
    None
        The assertions raise if acknowledgments regress.
    """
    # Create alert first
    registry.register(sample_sensor_alert_event, persistence_count=1, cooldown_seconds=300)

    # Acknowledge it
    result = registry.acknowledge(sample_sensor_alert_event.alert_key, actor="test_user")

    assert result is True
    state = registry._states[sample_sensor_alert_event.alert_key]
    assert state.acknowledged is True
    assert state.acknowledged_by == "test_user"


def test_acknowledge_nonexistent_alert_returns_false(registry):
    """Test that acknowledging nonexistent alert returns False.

    Parameters
    ----------
    registry : AlertRegistry
        Registry instance under test.

    Returns
    -------
    None
        The assertions raise if acknowledgments regress.
    """
    result = registry.acknowledge("nonexistent_alert", actor="test_user")
    assert result is False


def test_acknowledged_alert_still_updates_after_cooldown(registry, sample_sensor_alert_event):
    """Test that acknowledged alerts can still trigger UPDATED after cooldown.

    Parameters
    ----------
    registry : AlertRegistry
        Registry instance under test.
    sample_sensor_alert_event : SensorAlertEvent
        Sample alert event to register.

    Returns
    -------
    None
        The assertions raise if cooldown handling regresses.
    """
    cooldown_seconds = 0.1

    # Create and acknowledge alert
    registry.register(
        sample_sensor_alert_event, persistence_count=1, cooldown_seconds=cooldown_seconds
    )
    registry.acknowledge(sample_sensor_alert_event.alert_key, actor="test_user")

    # Wait for cooldown
    time.sleep(cooldown_seconds + 0.05)

    # Should still get ACTIVE status even though acknowledged
    event = registry.register(
        sample_sensor_alert_event, persistence_count=1, cooldown_seconds=cooldown_seconds
    )
    assert event == AlertStatus.ACTIVE

    # Acknowledged flag should remain
    state = registry._states[sample_sensor_alert_event.alert_key]
    assert state.acknowledged is True


def test_clear_removes_alert_state(registry, sample_sensor_alert_event):
    """Test that clearing an alert removes it from registry.

    Parameters
    ----------
    registry : AlertRegistry
        Registry instance under test.
    sample_sensor_alert_event : SensorAlertEvent
        Sample alert event to register.

    Returns
    -------
    None
        The assertions raise if clearing regresses.
    """
    # Create alert
    registry.register(sample_sensor_alert_event, persistence_count=1, cooldown_seconds=300)
    assert sample_sensor_alert_event.alert_key in registry._states

    # Clear it
    result = registry.clear(sample_sensor_alert_event.alert_key)

    assert result is True
    assert sample_sensor_alert_event.alert_key not in registry._states


def test_clear_nonexistent_alert_returns_false(registry):
    """Test that clearing nonexistent alert returns False.

    Parameters
    ----------
    registry : AlertRegistry
        Registry instance under test.

    Returns
    -------
    None
        The assertions raise if clearing regresses.
    """
    result = registry.clear("nonexistent_alert")
    assert result is False


def test_cleared_alert_can_be_recreated(registry, sample_sensor_alert_event):
    """Test that a cleared alert can be recreated from scratch.

    Parameters
    ----------
    registry : AlertRegistry
        Registry instance under test.
    sample_sensor_alert_event : SensorAlertEvent
        Sample alert event to register.

    Returns
    -------
    None
        The assertions raise if clearing regresses.
    """
    # Create, then clear
    registry.register(sample_sensor_alert_event, persistence_count=1, cooldown_seconds=300)
    registry.clear(sample_sensor_alert_event.alert_key)

    # Re-register should create new alert
    event = registry.register(sample_sensor_alert_event, persistence_count=1, cooldown_seconds=300)
    assert event == AlertStatus.ACTIVE

    state = registry._states[sample_sensor_alert_event.alert_key]
    assert state.occurrences == 1
    assert not state.acknowledged


def test_external_submission_uses_provided_alert_id(registry):
    """Test that external submissions (non-rule) use the provided alert_id.

    Parameters
    ----------
    registry : AlertRegistry
        Registry instance under test.

    Returns
    -------
    None
        The assertions raise if external submissions regress.
    """
    # External submission with custom alert_id
    from dt.communication.dataclasses.alerts.alert_record import ExternalAlertEvent

    external_candidate = ExternalAlertEvent(
        alert_key="external-ai-alert-123",  # Custom ID, not rule-based
        plant_id=1,
        timestamp=time.time(),
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.CRITICAL,
        message="AI detected anomaly",
        correlation_id="corr-ai-1",
        metadata={"anomaly_score": "0.95"},
    )

    event = registry.register(external_candidate, persistence_count=1, cooldown_seconds=120)

    assert event == AlertStatus.ACTIVE
    assert "external-ai-alert-123" in registry._states


def test_persistence_counter_resets_on_clear(registry, sample_sensor_alert_event):
    """Test that clearing an alert resets its persistence counter.

    Parameters
    ----------
    registry : AlertRegistry
        Registry instance under test.
    sample_sensor_alert_event : SensorAlertEvent
        Sample alert event to register.

    Returns
    -------
    None
        The assertions raise if clearing regresses.
    """
    # Register twice (persistence=3)
    registry.register(sample_sensor_alert_event, persistence_count=3, cooldown_seconds=300)
    registry.register(sample_sensor_alert_event, persistence_count=3, cooldown_seconds=300)

    # Clear the alert
    registry.clear(sample_sensor_alert_event.alert_key)

    # Register again - should need 3 occurrences again, not 1
    event1 = registry.register(sample_sensor_alert_event, persistence_count=3, cooldown_seconds=300)
    assert event1 == AlertStatus.IGNORED

    event2 = registry.register(sample_sensor_alert_event, persistence_count=3, cooldown_seconds=300)
    assert event2 == AlertStatus.IGNORED

    event3 = registry.register(sample_sensor_alert_event, persistence_count=3, cooldown_seconds=300)
    assert event3 == AlertStatus.ACTIVE


def test_correlation_id_updates_with_each_occurrence(registry, sample_sensor_alert_event):
    """Test that correlation_id is updated with each alert occurrence.

    Parameters
    ----------
    registry : AlertRegistry
        Registry instance under test.
    sample_sensor_alert_event : SensorAlertEvent
        Sample alert event to register.

    Returns
    -------
    None
        The assertions raise if correlation tracking regresses.
    """
    registry.register(sample_sensor_alert_event, persistence_count=1, cooldown_seconds=0.1)
    state = registry._states[sample_sensor_alert_event.alert_key]
    assert state.correlation_id == "test-corr-123"

    time.sleep(0.15)

    updated_candidate = SensorAlertEvent(
        alert_key=sample_sensor_alert_event.alert_key,
        plant_id=sample_sensor_alert_event.plant_id,
        timestamp=time.time(),
        status=AlertStatus.ACTIVE,
        severity=sample_sensor_alert_event.severity,
        message=sample_sensor_alert_event.message,
        correlation_id="test-corr-456",
        reading=sample_sensor_alert_event.reading,
        threshold_op=sample_sensor_alert_event.threshold_op,
        threshold_value=sample_sensor_alert_event.threshold_value,
    )

    registry.register(updated_candidate, persistence_count=1, cooldown_seconds=1)

    state = registry._states[sample_sensor_alert_event.alert_key]
    assert state.correlation_id == "test-corr-456"


def test_message_updates_with_each_occurrence(registry, sample_sensor_alert_event):
    """Test that message is updated with each alert occurrence.

    Parameters
    ----------
    registry : AlertRegistry
        Registry instance under test.
    sample_sensor_alert_event : SensorAlertEvent
        Sample alert event to register.

    Returns
    -------
    None
        The assertions raise if message updates regress.
    """
    registry.register(sample_sensor_alert_event, persistence_count=1, cooldown_seconds=0.1)
    state = registry._states[sample_sensor_alert_event.alert_key]
    assert "38°C" in state.message

    time.sleep(0.15)

    updated_reading = ProcessedSensorData(
        plant_id=sample_sensor_alert_event.reading.plant_id,
        sensor_id=sample_sensor_alert_event.reading.sensor_id,
        timestamp=1234567900.0,
        value=42.0,
        unit=sample_sensor_alert_event.reading.unit,
        topic=sample_sensor_alert_event.reading.topic,
        correlation_id=sample_sensor_alert_event.correlation_id,
        flags=sample_sensor_alert_event.reading.flags,
        dq_score=sample_sensor_alert_event.reading.dq_score,
        imputed=sample_sensor_alert_event.reading.imputed,
    )

    updated_candidate = SensorAlertEvent(
        alert_key=sample_sensor_alert_event.alert_key,
        plant_id=sample_sensor_alert_event.plant_id,
        timestamp=updated_reading.timestamp,
        status=AlertStatus.ACTIVE,
        severity=sample_sensor_alert_event.severity,
        message="Temperature exceeds 35°C (actual: 42°C)",
        correlation_id=sample_sensor_alert_event.correlation_id,
        reading=updated_reading,
        threshold_op=sample_sensor_alert_event.threshold_op,
        threshold_value=sample_sensor_alert_event.threshold_value,
    )

    registry.register(updated_candidate, persistence_count=1, cooldown_seconds=1)

    state = registry._states[sample_sensor_alert_event.alert_key]
    assert "42°C" in state.message


def test_timestamps_are_updated_correctly(registry, sample_sensor_alert_event):
    """Test that first_seen and last_seen timestamps are maintained.

    Parameters
    ----------
    registry : AlertRegistry
        Registry instance under test.
    sample_sensor_alert_event : SensorAlertEvent
        Sample alert event to register.

    Returns
    -------
    None
        The assertions raise if timestamps regress.
    """
    before_creation = time.time()
    registry.register(sample_sensor_alert_event, persistence_count=1, cooldown_seconds=0.1)
    after_creation = time.time()

    state = registry._states[sample_sensor_alert_event.alert_key]
    assert before_creation <= state.first_seen <= after_creation
    assert state.first_seen == state.last_seen  # Same on first occurrence

    time.sleep(0.15)
    before_update = time.time()
    registry.register(sample_sensor_alert_event, persistence_count=1, cooldown_seconds=0.1)
    after_update = time.time()

    state = registry._states[sample_sensor_alert_event.alert_key]
    assert before_update <= state.last_seen <= after_update
    assert state.last_seen > state.first_seen  # last_seen should be updated


def test_restore_state_hydrates_registry(registry):
    """Test that restore_state populates the registry from events.

    Parameters
    ----------
    registry : AlertRegistry
        Registry instance under test.

    Returns
    -------
    None
        The assertions raise if restoration regresses.
    """
    timestamp = time.time()

    # 1. Sensor Event
    reading = ProcessedSensorData(
        plant_id=1,
        sensor_id=1,
        timestamp=timestamp,
        value=50.0,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="corr-1",
        flags={},
        dq_score=1.0,
        imputed=False,
    )

    sensor_event = SensorAlertEvent(
        alert_key="high_temp:temperature",
        plant_id=1,
        timestamp=timestamp,
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.WARNING,
        message="Temp too high",
        correlation_id="corr-1",
        reading=reading,
    )

    # 2. External Event
    external_event = ExternalAlertEvent(
        alert_key="ai_anomaly:vision",
        plant_id=1,
        timestamp=timestamp,
        status=AlertStatus.ACKNOWLEDGED,
        severity=SeverityLevel.CRITICAL,
        message="Intruder detected",
        correlation_id="corr-2",
        acknowledged_by="guard",
        metadata={},
    )

    events = [sensor_event, external_event]

    # Execute Restore
    registry.restore_state(events)

    # Verify State 1 (Sensor)
    state1 = registry.get_alert_state("high_temp:temperature")
    assert state1 is not None
    assert state1.plant_id == 1
    assert state1.rule_id == "high_temp"
    assert state1.source == "temperature"
    assert state1.occurrences == 1
    assert state1.acknowledged is False
    assert state1.cooldown_until is not None

    # Verify State 2 (External + Acknowledged)
    state2 = registry.get_alert_state("ai_anomaly:vision")
    assert state2 is not None
    assert state2.rule_id is None  # External events have no rule_id
    # Source extraction for external events splits by colon if present
    assert state2.source == "vision"
    assert state2.severity == SeverityLevel.CRITICAL
    assert state2.acknowledged is True
    assert state2.acknowledged_by == "guard"
