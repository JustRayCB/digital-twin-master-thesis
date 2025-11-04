"""Tests for alert event publisher."""

from unittest.mock import Mock

import pytest

from dt.alerts.config.alert_rule import SeverityLevel
from dt.alerts.state.models import AlertLifecycleEvent
from dt.communication.dataclasses.alerts import CandidateAlert
from dt.communication import Topics


@pytest.fixture
def mock_messaging_service():
    """Create a mock MessagingService."""
    mock = Mock()
    mock.publish = Mock(return_value=True)
    return mock


@pytest.fixture
def publisher(mock_messaging_service):
    """Create AlertPublisher with mocked messaging service."""
    from dt.alerts.engine.publisher import AlertPublisher

    return AlertPublisher(mock_messaging_service, plant_id=1)


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


def test_publish_created_event(publisher, mock_messaging_service, sample_candidate):
    """Test publishing CREATED lifecycle event."""
    publisher.publish(AlertLifecycleEvent.CREATED, sample_candidate)

    # Verify publish was called on messaging service
    mock_messaging_service.publish.assert_called_once()

    # Extract the call arguments
    call_args = mock_messaging_service.publish.call_args
    topic = call_args[0][0]
    alert_message = call_args[0][1]

    # Verify correct topic
    assert topic == Topics.ALERTS

    # Verify AlertMessage envelope structure
    assert alert_message.event == "created"
    assert alert_message.alert_id == sample_candidate.alert_id
    assert alert_message.plant_id == 1
    assert alert_message.actor is None

    # Verify full alert details are preserved
    assert alert_message.alert is not None
    assert alert_message.alert.alert_id == sample_candidate.alert_id
    assert alert_message.alert.rule_id == sample_candidate.rule_id
    assert alert_message.alert.source == sample_candidate.source
    assert alert_message.alert.severity == sample_candidate.severity
    assert alert_message.alert.message == sample_candidate.message
    assert alert_message.alert.correlation_id == sample_candidate.correlation_id
    assert alert_message.alert.payload == sample_candidate.payload


def test_publish_updated_event(publisher, mock_messaging_service, sample_candidate):
    """Test publishing UPDATED lifecycle event."""
    publisher.publish(AlertLifecycleEvent.UPDATED, sample_candidate)

    # Verify publish was called
    assert mock_messaging_service.publish.called
    call_args = mock_messaging_service.publish.call_args
    alert_message = call_args[0][1]

    # Verify event data is correct
    assert alert_message.event == "updated"
    assert alert_message.alert_id == sample_candidate.alert_id
    assert alert_message.alert is not None


def test_publish_acknowledged_event(publisher, mock_messaging_service):
    """Test publishing ACKNOWLEDGED lifecycle event with alert_id and actor."""
    alert_id = "test_alert_123"
    actor = "user@example.com"

    publisher.publish(AlertLifecycleEvent.ACKNOWLEDGED, alert_id, actor=actor)

    # Verify publish was called
    assert mock_messaging_service.publish.called
    call_args = mock_messaging_service.publish.call_args
    topic = call_args[0][0]
    alert_message = call_args[0][1]

    # Verify correct topic
    assert topic == Topics.ALERTS

    # Verify AlertMessage structure for lifecycle event
    assert alert_message.event == "acknowledged"
    assert alert_message.alert_id == alert_id
    assert alert_message.actor == actor
    assert alert_message.alert is None  # No full alert details for lifecycle events


def test_publish_cleared_event(publisher, mock_messaging_service):
    """Test publishing CLEARED lifecycle event with alert_id."""
    alert_id = "test_alert_456"

    publisher.publish(AlertLifecycleEvent.CLEARED, alert_id, actor=None)

    # Verify publish was called
    assert mock_messaging_service.publish.called
    call_args = mock_messaging_service.publish.call_args
    alert_message = call_args[0][1]

    # Verify AlertMessage structure
    assert alert_message.event == "cleared"
    assert alert_message.alert_id == alert_id
    assert alert_message.actor is None
    assert alert_message.alert is None


def test_publish_multiple_events(publisher, mock_messaging_service, sample_candidate):
    """Test publishing multiple events in sequence."""
    # Create alert
    publisher.publish(AlertLifecycleEvent.CREATED, sample_candidate)

    # Update alert
    publisher.publish(AlertLifecycleEvent.UPDATED, sample_candidate)

    # Acknowledge alert
    publisher.publish(
        AlertLifecycleEvent.ACKNOWLEDGED, sample_candidate.alert_id, actor="test_user"
    )

    # Verify all three calls were made
    assert mock_messaging_service.publish.call_count == 3


def test_publish_with_external_submission(publisher, mock_messaging_service):
    """Test publishing alert from external submission (no rule_id)."""
    external_candidate = CandidateAlert(
        alert_id="manual_alert_001",
        rule_id=None,  # External submissions don't have rule_id
        source="manual",
        severity=SeverityLevel.CRITICAL,
        message="Manual alert submitted by user",
        correlation_id="ext-corr-789",
        payload={"submission_type": "external", "timestamp": 1234567890.0},
        persistence_count=1,
        cooldown_seconds=300,
    )

    publisher.publish(AlertLifecycleEvent.CREATED, external_candidate)

    # Verify publish was called
    assert mock_messaging_service.publish.called
    call_args = mock_messaging_service.publish.call_args
    alert_message = call_args[0][1]

    # Verify event data preserves all context
    assert alert_message.alert_id == "manual_alert_001"
    assert alert_message.alert is not None
    assert alert_message.alert.rule_id is None
    assert alert_message.alert.severity == SeverityLevel.CRITICAL


def test_publish_preserves_correlation_id(publisher, mock_messaging_service, sample_candidate):
    """Test that correlation ID is preserved in published events."""
    publisher.publish(AlertLifecycleEvent.CREATED, sample_candidate)

    call_args = mock_messaging_service.publish.call_args
    alert_message = call_args[0][1]

    # Verify correlation_id is preserved in the alert details
    assert alert_message.alert is not None
    assert alert_message.alert.correlation_id == sample_candidate.correlation_id
