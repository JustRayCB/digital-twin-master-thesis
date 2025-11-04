"""Tests for alert service REST API."""

import json
from unittest.mock import Mock

import pytest

from dt.alerts.config.alert_rule import SeverityLevel
from dt.alerts.state.models import AlertLifecycleEvent, AlertState
from dt.alerts.state.registry import AlertRegistry


@pytest.fixture
def registry():
    """Create a mock alert registry."""
    return Mock(spec=AlertRegistry)


@pytest.fixture
def publisher():
    """Create a mock alert publisher."""
    return Mock()


@pytest.fixture
def rule_manager():
    """Create a mock rule manager."""
    mock = Mock()
    mock.rules = []
    return mock


@pytest.fixture
def app(registry, publisher, rule_manager):
    """Create Flask test app with mocked dependencies."""
    from dt.alerts.api import create_alert_blueprint

    from flask import Flask

    app = Flask(__name__)

    # Create blueprints with dependency injection
    alerts_bp, rules_bp = create_alert_blueprint(
        registry=registry, publisher=publisher, rule_manager=rule_manager
    )
    app.register_blueprint(alerts_bp)
    app.register_blueprint(rules_bp)

    return app


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


def test_submit_alert_success(client, registry, publisher):
    """Test successful alert submission returns 202 with alert ID."""
    # Configure mock registry to return CREATED event
    registry.register.return_value = AlertLifecycleEvent.CREATED

    payload = {
        "alert_id": "manual_alert_123",
        "source": "manual",
        "severity": "warning",
        "message": "Manual alert test",
        "correlation_id": "test-corr-456",
        "persistence_count": 1,
        "cooldown_seconds": 60,
    }

    response = client.post(
        "/alerts/submit", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 202
    data = json.loads(response.data)
    assert "alert_id" in data
    assert data["alert_id"] == "manual_alert_123"

    # Verify registry was called
    registry.register.assert_called_once()


def test_submit_alert_invalid_json(client):
    """Test alert submission with invalid JSON returns 400."""
    response = client.post(
        "/alerts/submit", data="not json", content_type="application/json"
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data


def test_submit_alert_missing_fields(client):
    """Test alert submission with missing required fields returns 400."""
    payload = {
        "source": "manual",
        "message": "Missing alert_id and severity",
    }

    response = client.post(
        "/alerts/submit", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data


def test_submit_alert_invalid_severity(client):
    """Test alert submission with invalid severity returns 400."""
    payload = {
        "alert_id": "test_alert",
        "source": "manual",
        "severity": "invalid_severity",
        "message": "Test message",
        "correlation_id": "test-corr-789",
    }

    response = client.post(
        "/alerts/submit", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data


def test_acknowledge_alert_success(client, registry):
    """Test successful alert acknowledgment returns 200."""
    # Configure mock registry to return True
    registry.acknowledge.return_value = True

    payload = {"actor": "user@example.com"}

    response = client.post(
        "/alerts/test_alert_id/acknowledge",
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "acknowledged"

    # Verify registry was called with correct parameters
    registry.acknowledge.assert_called_once_with("test_alert_id", "user@example.com")


def test_acknowledge_alert_not_found(client, registry):
    """Test acknowledging non-existent alert returns 404."""
    # Configure mock registry to return False (alert not found)
    registry.acknowledge.return_value = False

    payload = {"actor": "user@example.com"}

    response = client.post(
        "/alerts/nonexistent_alert/acknowledge",
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 404
    data = json.loads(response.data)
    assert "error" in data


def test_acknowledge_alert_missing_actor(client):
    """Test acknowledging alert without actor returns 400."""
    response = client.post(
        "/alerts/test_alert_id/acknowledge",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data


def test_clear_alert_success(client, registry):
    """Test successful alert clearing returns 200."""
    # Configure mock registry to return True
    registry.clear.return_value = True

    response = client.post("/alerts/test_alert_id/clear")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "cleared"

    # Verify registry was called
    registry.clear.assert_called_once_with("test_alert_id")


def test_clear_alert_not_found(client, registry):
    """Test clearing non-existent alert returns 404."""
    # Configure mock registry to return False (alert not found)
    registry.clear.return_value = False

    response = client.post("/alerts/nonexistent_alert/clear")

    assert response.status_code == 404
    data = json.loads(response.data)
    assert "error" in data


def test_list_active_alerts(client, registry):
    """Test listing active alerts returns correct data."""
    # Create mock alert states
    mock_alerts = [
        AlertState(
            alert_id="alert1",
            rule_id="temp_high",
            source="temperature",
            severity=SeverityLevel.WARNING,
            message="Temperature too high",
            first_seen=1234567890.0,
            last_seen=1234567900.0,
            occurrences=3,
            acknowledged=False,
            acknowledged_by=None,
            cooldown_until=1234568000.0,
            correlation_id="corr-123",
        ),
        AlertState(
            alert_id="alert2",
            rule_id="moisture_low",
            source="soil_moisture",
            severity=SeverityLevel.CRITICAL,
            message="Soil moisture critically low",
            first_seen=1234567800.0,
            last_seen=1234567850.0,
            occurrences=5,
            acknowledged=True,
            acknowledged_by="user@example.com",
            cooldown_until=1234568100.0,
            correlation_id="corr-456",
        ),
    ]

    registry.get_active_alerts.return_value = mock_alerts

    response = client.get("/alerts/active")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) == 2

    # Verify first alert
    assert data[0]["alert_id"] == "alert1"
    assert data[0]["severity"] == "warning"
    assert data[0]["acknowledged"] is False

    # Verify second alert
    assert data[1]["alert_id"] == "alert2"
    assert data[1]["severity"] == "critical"
    assert data[1]["acknowledged"] is True
    assert data[1]["acknowledged_by"] == "user@example.com"


def test_list_alert_rules(client, rule_manager):
    """Test listing alert rules returns configuration."""
    # Create mock rules
    from dt.alerts.config.alert_rule import (
        AlertCondition,
        AlertRule,
        ConditionType,
        EvaluationStage,
        SeverityLevel,
    )

    mock_rules = [
        AlertRule(
            rule_id="temp_high",
            name="High Temperature",
            description="Temperature exceeds {threshold}°C",
            severity=SeverityLevel.WARNING,
            evaluation_stage=EvaluationStage.PROCESSED,
            source="temperature",
            condition=AlertCondition(
                type=ConditionType.THRESHOLD, params={"operator": ">", "threshold": 35.0}
            ),
            persistence_count=3,
            cooldown_seconds=300,
        )
    ]

    rule_manager.rules = mock_rules

    response = client.get("/alert-rules")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) == 1
    assert data[0]["rule_id"] == "temp_high"
    assert data[0]["name"] == "High Temperature"
    assert data[0]["severity"] == "warning"


def test_submit_alert_publishes_updated_event(client, registry, publisher):
    """Test that UPDATED events are published to downstream consumers."""
    # Configure mock registry to return UPDATED event
    registry.register.return_value = AlertLifecycleEvent.UPDATED

    payload = {
        "alert_id": "repeated_alert",
        "source": "temperature",
        "severity": "warning",
        "message": "Temperature alert repeated after cooldown",
        "correlation_id": "test-corr-updated",
        "persistence_count": 1,
        "cooldown_seconds": 60,
    }

    response = client.post(
        "/alerts/submit", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 202
    data = json.loads(response.data)
    assert data["event"] == "updated"

    # Verify publisher was called with UPDATED event
    publisher.publish.assert_called_once()
    call_args = publisher.publish.call_args
    assert call_args[0][0] == AlertLifecycleEvent.UPDATED


def test_submit_alert_does_not_publish_suppressed_event(client, registry, publisher):
    """Test that SUPPRESSED events are not published (within cooldown)."""
    # Configure mock registry to return SUPPRESSED event
    registry.register.return_value = AlertLifecycleEvent.SUPPRESSED

    payload = {
        "alert_id": "suppressed_alert",
        "source": "temperature",
        "severity": "warning",
        "message": "Alert within cooldown period",
        "correlation_id": "test-corr-suppressed",
        "persistence_count": 1,
        "cooldown_seconds": 60,
    }

    response = client.post(
        "/alerts/submit", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 202
    data = json.loads(response.data)
    assert data["event"] == "suppressed"

    # Verify publisher was NOT called for suppressed events
    publisher.publish.assert_not_called()


def test_submit_alert_validation_empty_alert_id(client):
    """Test that empty alert_id is rejected."""
    payload = {
        "alert_id": "",
        "source": "manual",
        "severity": "warning",
        "message": "Test",
        "correlation_id": "test-corr",
    }

    response = client.post(
        "/alerts/submit", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "alert_id" in data["error"]


def test_submit_alert_validation_negative_persistence_count(client):
    """Test that negative persistence_count is rejected."""
    payload = {
        "alert_id": "test_alert",
        "source": "manual",
        "severity": "warning",
        "message": "Test",
        "correlation_id": "test-corr",
        "persistence_count": -1,
    }

    response = client.post(
        "/alerts/submit", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "persistence_count" in data["error"]


def test_submit_alert_validation_negative_cooldown(client):
    """Test that negative cooldown_seconds is rejected."""
    payload = {
        "alert_id": "test_alert",
        "source": "manual",
        "severity": "warning",
        "message": "Test",
        "correlation_id": "test-corr",
        "cooldown_seconds": -10,
    }

    response = client.post(
        "/alerts/submit", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "cooldown_seconds" in data["error"]
