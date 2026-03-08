"""Tests for alert service REST API."""

import json

import pytest

from dt.alerts.registry import AlertRegistry
from dt.alerts.rule_manager import AlertRuleManager
from dt.alerts.rules import SeverityLevel
from dt.alerts.state import AlertState
from dt.communication.dataclasses.alerts.alert_record import (
    AlertHistoryEvent,
    AlertStatus,
    ExternalAlertEvent,
)
from tests.alerts.helpers import poll_alert_event

pytestmark = [pytest.mark.requires_kafka, pytest.mark.requires_timescale]


@pytest.fixture
def rule_manager() -> AlertRuleManager:
    """Create an empty alert rule manager.

    Returns
    -------
    AlertRuleManager
        Rule manager with no configured rules.
    """
    return AlertRuleManager([])


@pytest.fixture
def app(registry: AlertRegistry, publisher, rule_manager: AlertRuleManager):
    """Create Flask test app with injected dependencies.

    Parameters
    ----------
    registry : AlertRegistry
        Registry instance used by the API.
    publisher : AlertPublisher
        Publisher emitting alert events to Kafka.
    rule_manager : AlertRuleManager
        Alert rule manager instance.

    Returns
    -------
    flask.Flask
        Flask app with alert blueprints registered.
    """
    from flask import Flask

    from dt.alerts.api import create_alert_blueprint

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
    """Create Flask test client.

    Parameters
    ----------
    app : flask.Flask
        Flask app fixture to test against.

    Returns
    -------
    flask.testing.FlaskClient
        Client for issuing requests to the app.
    """
    return app.test_client()


@pytest.fixture
def plant_id(sample_plant_id) -> int:
    """Return a valid plant identifier for API tests.

    Parameters
    ----------
    sample_plant_id : int
        Plant identifier from the test database.

    Returns
    -------
    int
        Plant identifier used in API payloads.
    """
    return sample_plant_id


def test_submit_alert_success(client, registry, publisher, alerts_consumer, plant_id):
    """Test successful alert submission returns 202 with alert ID.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask test client.
    registry : AlertRegistry
        Registry used for alert state management.
    publisher : AlertPublisher
        Publisher emitting alert events to Kafka.

    Returns
    -------
    None
        The assertions raise if submission handling regresses.
    """

    payload = {
        "alert_key": "manual_alert_123",
        "plant_id": plant_id,
        "severity": "warning",
        "message": "Manual alert test",
        "correlation_id": "test-corr-456",
        "persistence_count": 1,
        "cooldown_seconds": 60,
        "metadata": {},
    }

    response = client.post(
        "/alerts/submit", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 202
    data = json.loads(response.data)
    assert data["alert_key"] == "manual_alert_123"
    assert data["status"] == "active"

    # Verify registry state was created
    state = registry.get_alert_state("manual_alert_123")
    assert state is not None
    assert state.plant_id == plant_id
    assert state.severity == SeverityLevel.WARNING

    event = poll_alert_event(alerts_consumer)
    assert event is not None
    assert event.alert_key == "manual_alert_123"
    assert event.status == AlertStatus.ACTIVE
    assert event.correlation_id == "test-corr-456"
    assert event.severity == SeverityLevel.WARNING
    assert isinstance(event, ExternalAlertEvent)


def test_submit_alert_invalid_json(client):
    """Test alert submission with invalid JSON returns 400.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask test client.

    Returns
    -------
    None
        The assertions raise if JSON validation regresses.
    """
    response = client.post("/alerts/submit", data="not json", content_type="application/json")

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data


def test_submit_alert_missing_fields(client):
    """Test alert submission with missing required fields returns 400.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask test client.

    Returns
    -------
    None
        The assertions raise if required field validation regresses.
    """
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


def test_submit_alert_invalid_severity(client, plant_id):
    """Test alert submission with invalid severity returns 400.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask test client.

    Returns
    -------
    None
        The assertions raise if severity validation regresses.
    """
    payload = {
        "alert_key": "test_alert",
        "plant_id": plant_id,
        "severity": "invalid_severity",
        "message": "Test message",
        "correlation_id": "test-corr-789",
        "metadata": {},
    }

    response = client.post(
        "/alerts/submit", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data


def test_acknowledge_alert_success(client, registry, publisher, alerts_consumer, plant_id):
    """Test successful alert acknowledgment returns 200.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask test client.
    registry : AlertRegistry
        Registry used for alert state management.
    publisher : AlertPublisher
        Publisher emitting alert events to Kafka.

    Returns
    -------
    None
        The assertions raise if acknowledgment handling regresses.
    """
    registry._states["test_alert_id"] = AlertState(
        alert_id="test_alert_id",
        plant_id=plant_id,
        rule_id=None,
        source="external",
        severity=SeverityLevel.WARNING,
        message="Manual alert test",
        first_seen=1.0,
        last_seen=1.0,
        occurrences=1,
        acknowledged=False,
        acknowledged_by=None,
        cooldown_until=None,
        correlation_id="corr-ack",
    )

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
    state = registry.get_alert_state("test_alert_id")
    assert state is not None
    assert state.acknowledged is True
    assert state.acknowledged_by == "user@example.com"
    event = poll_alert_event(alerts_consumer)
    assert event is not None
    assert event.alert_key == "test_alert_id"
    assert event.status == AlertStatus.ACKNOWLEDGED
    assert event.correlation_id == "corr-ack"
    assert type(event) is AlertHistoryEvent
    assert event.plant_id == plant_id
    assert event.status == AlertStatus.ACKNOWLEDGED
    assert event.acknowledged_by == "user@example.com"
    assert event.correlation_id == "corr-ack"


def test_acknowledge_alert_not_found(client, registry):
    """Test acknowledging non-existent alert returns 404.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask test client.
    registry : AlertRegistry
        Registry used for alert state management.

    Returns
    -------
    None
        The assertions raise if missing alert handling regresses.
    """

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
    """Test acknowledging alert without actor returns 400.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask test client.

    Returns
    -------
    None
        The assertions raise if actor validation regresses.
    """
    response = client.post(
        "/alerts/test_alert_id/acknowledge",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data


def test_clear_alert_success(client, registry, publisher, alerts_consumer, plant_id):
    """Test successful alert clearing returns 200.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask test client.
    registry : AlertRegistry
        Registry used for alert state management.
    publisher : AlertPublisher
        Publisher emitting alert events to Kafka.

    Returns
    -------
    None
        The assertions raise if clear handling regresses.
    """
    registry._states["test_alert_id"] = AlertState(
        alert_id="test_alert_id",
        plant_id=plant_id,
        rule_id=None,
        source="external",
        severity=SeverityLevel.WARNING,
        message="Manual alert test",
        first_seen=1.0,
        last_seen=1.0,
        occurrences=1,
        acknowledged=False,
        acknowledged_by=None,
        cooldown_until=None,
        correlation_id="corr-clear",
    )

    response = client.post("/alerts/test_alert_id/clear")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "cleared"

    # Verify registry was called
    assert registry.get_alert_state("test_alert_id") is None
    event = poll_alert_event(alerts_consumer)
    assert event is not None
    assert event.alert_key == "test_alert_id"
    assert event.status == AlertStatus.CLEARED
    assert event.correlation_id == "corr-clear"
    assert type(event) is AlertHistoryEvent
    assert event.plant_id == plant_id
    assert event.status == AlertStatus.CLEARED
    assert event.correlation_id == "corr-clear"


def test_clear_alert_not_found(client, registry):
    """Test clearing non-existent alert returns 404.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask test client.
    registry : AlertRegistry
        Registry used for alert state management.

    Returns
    -------
    None
        The assertions raise if missing alert handling regresses.
    """

    response = client.post("/alerts/nonexistent_alert/clear")

    assert response.status_code == 404
    data = json.loads(response.data)
    assert "error" in data


def test_list_alert_rules(client, rule_manager):
    """Test listing alert rules returns configuration.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask test client.
    rule_manager : AlertRuleManager
        Rule manager used to serve rules.

    Returns
    -------
    None
        The assertions raise if rule listing regresses.
    """
    # Create mock rules
    from dt.alerts.rules import (
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

    rule_manager._rules = mock_rules

    response = client.get("/alert-rules")

    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) == 1
    assert data[0]["rule_id"] == "temp_high"
    assert data[0]["name"] == "High Temperature"
    assert data[0]["severity"] == "warning"


def test_submit_alert_publishes_active_event(client, registry, publisher, alerts_consumer, plant_id):
    """Test that ACTIVE status is published to downstream consumers.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask test client.
    registry : AlertRegistry
        Registry used for alert state management.
    publisher : AlertPublisher
        Publisher emitting alert events to Kafka.

    Returns
    -------
    None
        The assertions raise if active publishing regresses.
    """

    payload = {
        "alert_key": "repeated_alert",
        "plant_id": plant_id,
        "severity": "warning",
        "message": "Temperature alert repeated after cooldown",
        "correlation_id": "test-corr-updated",
        "persistence_count": 1,
        "cooldown_seconds": 60,
        "metadata": {},
    }

    response = client.post(
        "/alerts/submit", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 202
    data = json.loads(response.data)
    assert data["status"] == "active"

    # Verify publisher was called with ACTIVE status
    event = poll_alert_event(alerts_consumer)
    assert event is not None
    assert event.alert_key == payload["alert_key"]
    assert event.status == AlertStatus.ACTIVE
    assert event.correlation_id == payload["correlation_id"]
    assert isinstance(event, ExternalAlertEvent)


def test_submit_alert_does_not_publish_ignored_event(
    client, registry, publisher, alerts_consumer, plant_id
):
    """Test that IGNORED status is not published (within cooldown).

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask test client.
    registry : AlertRegistry
        Registry used for alert state management.
    publisher : AlertPublisher
        Publisher emitting alert events to Kafka.

    Returns
    -------
    None
        The assertions raise if ignored alerts are published.
    """

    payload = {
        "alert_key": "suppressed_alert",
        "plant_id": plant_id,
        "severity": "warning",
        "message": "Alert within cooldown period",
        "correlation_id": "test-corr-suppressed",
        "persistence_count": 1,
        "cooldown_seconds": 60,
        "metadata": {},
    }

    first_response = client.post(
        "/alerts/submit", data=json.dumps(payload), content_type="application/json"
    )

    assert first_response.status_code == 202
    first_data = json.loads(first_response.data)
    assert first_data["status"] == "active"

    second_response = client.post(
        "/alerts/submit", data=json.dumps(payload), content_type="application/json"
    )

    assert second_response.status_code == 202
    second_data = json.loads(second_response.data)
    assert second_data["status"] == "ignored"

    first_event = poll_alert_event(alerts_consumer)
    assert first_event is not None

    second_event = poll_alert_event(alerts_consumer, timeout_seconds=2.0)
    assert second_event is None


def test_submit_alert_validation_empty_alert_id(client, plant_id):
    """Test that empty alert_id is rejected.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask test client.

    Returns
    -------
    None
        The assertions raise if empty IDs are accepted.
    """
    payload = {
        "alert_key": "",
        "plant_id": plant_id,
        "severity": "warning",
        "message": "Test",
        "correlation_id": "test-corr",
        "persistence_count": 1,
        "cooldown_seconds": 60,
        "metadata": {},
    }

    response = client.post(
        "/alerts/submit", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data


def test_submit_alert_validation_negative_persistence_count(client, plant_id):
    """Test that negative persistence_count is rejected.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask test client.

    Returns
    -------
    None
        The assertions raise if persistence validation regresses.
    """
    payload = {
        "alert_key": "test_alert",
        "plant_id": plant_id,
        "severity": "warning",
        "message": "Test",
        "correlation_id": "test-corr",
        "persistence_count": -1,
        "cooldown_seconds": 60,
        "metadata": {},
    }

    response = client.post(
        "/alerts/submit", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data


def test_submit_alert_validation_negative_cooldown(client, plant_id):
    """Test that negative cooldown_seconds is rejected.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask test client.

    Returns
    -------
    None
        The assertions raise if cooldown validation regresses.
    """
    payload = {
        "alert_key": "test_alert",
        "plant_id": plant_id,
        "severity": "warning",
        "message": "Test",
        "correlation_id": "test-corr",
        "persistence_count": 1,
        "cooldown_seconds": -10,
        "metadata": {},
    }

    response = client.post(
        "/alerts/submit", data=json.dumps(payload), content_type="application/json"
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data
