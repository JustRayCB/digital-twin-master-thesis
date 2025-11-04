"""Tests for alert registry state management."""

import time

import pytest

from dt.alerts.config.alert_rule import SeverityLevel
from dt.alerts.state.models import AlertLifecycleEvent
from dt.alerts.state.registry import AlertRegistry
from dt.communication.dataclasses.alerts import CandidateAlert


@pytest.fixture
def registry():
    """Create a fresh alert registry."""
    return AlertRegistry()


@pytest.fixture
def sample_candidate():
    """Create a sample candidate alert."""
    return CandidateAlert(
        alert_id="temp_high:temperature",
        rule_id="temp_high",
        source="temperature",
        severity=SeverityLevel.WARNING,
        message="Temperature exceeds 35°C (actual: 38°C)",
        correlation_id="test-corr-123",
        payload={"value": 38.0, "sensor_id": 101, "timestamp": 1234567890.0},
        persistence_count=1,
        cooldown_seconds=300,
    )


def test_first_occurrence_below_persistence_is_ignored(registry, sample_candidate):
    """Test that first occurrence below persistence threshold is ignored."""
    sample_candidate.persistence_count = 3
    sample_candidate.cooldown_seconds = 300
    event = registry.register(sample_candidate)

    assert event == AlertLifecycleEvent.IGNORED
    # Alert should be tracked but not considered active yet
    assert sample_candidate.alert_id in registry._states


def test_persistence_threshold_creates_alert(registry, sample_candidate):
    """Test that reaching persistence threshold creates alert."""
    # First two occurrences should be ignored
    sample_candidate.persistence_count = 3
    sample_candidate.cooldown_seconds = 300

    event1 = registry.register(sample_candidate)
    assert event1 == AlertLifecycleEvent.IGNORED

    event2 = registry.register(sample_candidate)
    assert event2 == AlertLifecycleEvent.IGNORED

    # Third occurrence should create the alert
    event3 = registry.register(sample_candidate)
    assert event3 == AlertLifecycleEvent.CREATED

    # Verify alert state
    state = registry._states[sample_candidate.alert_id]
    assert state.occurrences == 3
    assert not state.acknowledged


def test_persistence_count_of_one_creates_immediately(registry, sample_candidate):
    """Test that persistence_count=1 creates alert on first occurrence."""
    sample_candidate.persistence_count = 1
    sample_candidate.cooldown_seconds = 300
    event = registry.register(sample_candidate)

    assert event == AlertLifecycleEvent.CREATED
    state = registry._states[sample_candidate.alert_id]
    assert state.occurrences == 1


def test_alert_within_cooldown_is_suppressed(registry, sample_candidate):
    """Test that alerts within cooldown period are suppressed."""
    # Create alert (persistence=1 for simplicity)
    sample_candidate.persistence_count = 1
    sample_candidate.cooldown_seconds = 300
    event1 = registry.register(sample_candidate)
    assert event1 == AlertLifecycleEvent.CREATED

    # Immediate re-occurrence should be suppressed
    event2 = registry.register(sample_candidate)
    assert event2 == AlertLifecycleEvent.SUPPRESSED


def test_alert_after_cooldown_is_updated(registry, sample_candidate):
    """Test that alerts after cooldown period trigger UPDATED event."""
    # Use very short cooldown for testing
    cooldown_seconds = 0.1

    sample_candidate.persistence_count = 1
    sample_candidate.cooldown_seconds = cooldown_seconds

    # Create alert
    event1 = registry.register(sample_candidate)
    assert event1 == AlertLifecycleEvent.CREATED

    # Wait for cooldown to expire
    time.sleep(cooldown_seconds + 0.05)

    # Next occurrence should trigger UPDATED
    event2 = registry.register(sample_candidate)
    assert event2 == AlertLifecycleEvent.UPDATED

    # Verify state was updated
    state = registry._states[sample_candidate.alert_id]
    assert state.occurrences == 2


def test_acknowledge_sets_flag_and_returns_true(registry, sample_candidate):
    """Test that acknowledging an alert sets the flag."""
    # Create alert first
    sample_candidate.persistence_count = 1
    sample_candidate.cooldown_seconds = 300
    registry.register(sample_candidate)

    # Acknowledge it
    result = registry.acknowledge(sample_candidate.alert_id, actor="test_user")

    assert result is True
    state = registry._states[sample_candidate.alert_id]
    assert state.acknowledged is True
    assert state.acknowledged_by == "test_user"


def test_acknowledge_nonexistent_alert_returns_false(registry):
    """Test that acknowledging nonexistent alert returns False."""
    result = registry.acknowledge("nonexistent_alert", actor="test_user")
    assert result is False


def test_acknowledged_alert_still_updates_after_cooldown(registry, sample_candidate):
    """Test that acknowledged alerts can still trigger UPDATED after cooldown."""
    cooldown_seconds = 0.1

    # Create and acknowledge alert
    sample_candidate.persistence_count = 1
    sample_candidate.cooldown_seconds = cooldown_seconds
    registry.register(sample_candidate)
    registry.acknowledge(sample_candidate.alert_id, actor="test_user")

    # Wait for cooldown
    time.sleep(cooldown_seconds + 0.05)

    # Should still get UPDATED event even though acknowledged
    event = registry.register(sample_candidate)
    assert event == AlertLifecycleEvent.UPDATED

    # Acknowledged flag should remain
    state = registry._states[sample_candidate.alert_id]
    assert state.acknowledged is True


def test_clear_removes_alert_state(registry, sample_candidate):
    """Test that clearing an alert removes it from registry."""
    # Create alert
    sample_candidate.persistence_count = 1
    sample_candidate.cooldown_seconds = 300
    registry.register(sample_candidate)
    assert sample_candidate.alert_id in registry._states

    # Clear it
    result = registry.clear(sample_candidate.alert_id)

    assert result is True
    assert sample_candidate.alert_id not in registry._states


def test_clear_nonexistent_alert_returns_false(registry):
    """Test that clearing nonexistent alert returns False."""
    result = registry.clear("nonexistent_alert")
    assert result is False


def test_cleared_alert_can_be_recreated(registry, sample_candidate):
    """Test that a cleared alert can be recreated from scratch."""
    # Create, then clear
    sample_candidate.persistence_count = 1
    sample_candidate.cooldown_seconds = 300
    registry.register(sample_candidate)
    registry.clear(sample_candidate.alert_id)

    # Re-register should create new alert
    event = registry.register(sample_candidate)
    assert event == AlertLifecycleEvent.CREATED

    state = registry._states[sample_candidate.alert_id]
    assert state.occurrences == 1
    assert not state.acknowledged


def test_get_active_alerts_returns_all_created_alerts(registry):
    """Test that get_active_alerts returns all alerts that have been created."""
    # Create multiple alerts with different IDs
    candidate1 = CandidateAlert(
        alert_id="temp_high:temperature",
        rule_id="temp_high",
        source="temperature",
        severity=SeverityLevel.WARNING,
        message="High temperature",
        correlation_id="corr-1",
        payload={},
        persistence_count=1,
        cooldown_seconds=300,
    )

    candidate2 = CandidateAlert(
        alert_id="moisture_low:soil_moisture",
        rule_id="moisture_low",
        source="soil_moisture",
        severity=SeverityLevel.CRITICAL,
        message="Low moisture",
        correlation_id="corr-2",
        payload={},
        persistence_count=1,
        cooldown_seconds=300,
    )

    # Register both with persistence=1
    registry.register(candidate1)
    registry.register(candidate2)

    # Get active alerts
    active = registry.get_active_alerts()

    assert len(active) == 2
    alert_ids = {alert.alert_id for alert in active}
    assert alert_ids == {"temp_high:temperature", "moisture_low:soil_moisture"}


def test_get_active_alerts_excludes_ignored_alerts(registry, sample_candidate):
    """Test that get_active_alerts excludes alerts below persistence threshold."""
    # Register with persistence=3, only once
    sample_candidate.persistence_count = 3
    sample_candidate.cooldown_seconds = 300
    registry.register(sample_candidate)

    # Should not be in active alerts yet
    active = registry.get_active_alerts()
    assert len(active) == 0


def test_external_submission_uses_provided_alert_id(registry):
    """Test that external submissions (non-rule) use the provided alert_id."""
    # External submission with custom alert_id
    external_candidate = CandidateAlert(
        alert_id="external-ai-alert-123",  # Custom ID, not rule-based
        rule_id=None,  # No rule
        source="ai_detector",
        severity=SeverityLevel.CRITICAL,
        message="AI detected anomaly",
        correlation_id="corr-ai-1",
        payload={"anomaly_score": 0.95},
        persistence_count=1,
        cooldown_seconds=120,
    )

    event = registry.register(external_candidate)

    assert event == AlertLifecycleEvent.CREATED
    assert "external-ai-alert-123" in registry._states


def test_persistence_counter_resets_on_clear(registry, sample_candidate):
    """Test that clearing an alert resets its persistence counter."""
    # Register twice (persistence=3)
    sample_candidate.persistence_count = 3
    sample_candidate.cooldown_seconds = 300
    registry.register(sample_candidate)
    registry.register(sample_candidate)

    # Clear the alert
    registry.clear(sample_candidate.alert_id)

    # Register again - should need 3 occurrences again, not 1
    event1 = registry.register(sample_candidate)
    assert event1 == AlertLifecycleEvent.IGNORED

    event2 = registry.register(sample_candidate)
    assert event2 == AlertLifecycleEvent.IGNORED

    event3 = registry.register(sample_candidate)
    assert event3 == AlertLifecycleEvent.CREATED


def test_correlation_id_updates_with_each_occurrence(registry, sample_candidate):
    """Test that correlation_id is updated with each alert occurrence."""
    # Create alert
    sample_candidate.persistence_count = 1
    sample_candidate.cooldown_seconds = 0.1
    registry.register(sample_candidate)
    state = registry._states[sample_candidate.alert_id]
    assert state.correlation_id == "test-corr-123"

    # Wait for cooldown
    time.sleep(0.15)

    # Register with new correlation_id
    updated_candidate = CandidateAlert(
        alert_id=sample_candidate.alert_id,
        rule_id=sample_candidate.rule_id,
        source=sample_candidate.source,
        severity=sample_candidate.severity,
        message=sample_candidate.message,
        correlation_id="test-corr-456",  # New correlation ID
        payload=sample_candidate.payload,
        persistence_count=1,
        cooldown_seconds=0.1,
    )

    registry.register(updated_candidate)

    # Correlation ID should be updated
    state = registry._states[sample_candidate.alert_id]
    assert state.correlation_id == "test-corr-456"


def test_message_updates_with_each_occurrence(registry, sample_candidate):
    """Test that message is updated with each alert occurrence."""
    # Create alert
    sample_candidate.persistence_count = 1
    sample_candidate.cooldown_seconds = 0.1
    registry.register(sample_candidate)
    state = registry._states[sample_candidate.alert_id]
    assert "38°C" in state.message

    # Wait for cooldown
    time.sleep(0.15)

    # Register with updated message
    updated_candidate = CandidateAlert(
        alert_id=sample_candidate.alert_id,
        rule_id=sample_candidate.rule_id,
        source=sample_candidate.source,
        severity=sample_candidate.severity,
        message="Temperature exceeds 35°C (actual: 42°C)",  # Updated message
        correlation_id=sample_candidate.correlation_id,
        payload={"value": 42.0, "sensor_id": 101, "timestamp": 1234567900.0},
        persistence_count=1,
        cooldown_seconds=0.1,
    )

    registry.register(updated_candidate)

    # Message should be updated
    state = registry._states[sample_candidate.alert_id]
    assert "42°C" in state.message


def test_timestamps_are_updated_correctly(registry, sample_candidate):
    """Test that first_seen and last_seen timestamps are maintained."""
    # Create alert
    sample_candidate.persistence_count = 1
    sample_candidate.cooldown_seconds = 0.1
    before_creation = time.time()
    registry.register(sample_candidate)
    after_creation = time.time()

    state = registry._states[sample_candidate.alert_id]
    assert before_creation <= state.first_seen <= after_creation
    assert state.first_seen == state.last_seen  # Same on first occurrence

    # Wait and register again
    time.sleep(0.15)
    before_update = time.time()
    registry.register(sample_candidate)
    after_update = time.time()

    state = registry._states[sample_candidate.alert_id]
    assert before_update <= state.last_seen <= after_update
    assert state.last_seen > state.first_seen  # last_seen should be updated
