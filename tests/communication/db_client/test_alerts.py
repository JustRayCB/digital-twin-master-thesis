from unittest.mock import MagicMock, patch

import pytest
import requests

from dt.alerts.rules import SeverityLevel
from dt.communication.dataclasses.alerts.alert_record import AlertDefinition, AlertHistoryEvent, AlertStatus
from dt.communication.dataclasses.queries import ActiveAlertsQuery, AlertHistoryQuery
from dt.communication.db_client import DatabaseApiClient
from dt.communication.topics import Topics


def test_get_alert_history_parses_polymorphic_events() -> None:
    """Parse sensor/external/base history events from HTTP payload.

    Returns
    -------
    None
        Assertions fail if polymorphic routing regresses.
    """
    client = DatabaseApiClient(base_url="http://localhost:5001")

    payload = [
        {
            "alert_key": "rule1:temp",
            "plant_id": 1,
            "timestamp": 1234567890.0,
            "status": "active",
            "severity": "warning",
            "message": "High temp",
            "correlation_id": "corr1",
            "reading": {
                "timestamp": 1234567890.0,
                "sensor_id": 1,
                "plant_id": 1,
                "topic": Topics.TEMPERATURE.value,
                "value": 25.5,
                "unit": "C",
                "correlation_id": "corr1",
                "flags": {},
                "dq_score": 1.0,
                "imputed": False,
            },
        },
        {
            "alert_key": "ai:anomaly",
            "plant_id": 1,
            "timestamp": 1234567891.0,
            "status": "active",
            "severity": "critical",
            "message": "Anomaly detected",
            "correlation_id": "corr2",
            "metadata": {"model": "demo"},
        },
        {
            "alert_key": "base:event",
            "plant_id": 1,
            "timestamp": 1234567892.0,
            "status": "acknowledged",
            "severity": "info",
            "message": "Acknowledged",
            "correlation_id": "corr3",
            "acknowledged_by": "ray",
            "acknowledged_ts": 1234567892.5,
        },
    ]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = payload
    mock_response.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_response):
        events = client.get_alert_history(AlertHistoryQuery(plant_id=1, limit=50))

    assert len(events) == 3
    assert events[0].severity is SeverityLevel.WARNING
    assert events[1].severity is SeverityLevel.CRITICAL
    assert isinstance(events[2], AlertHistoryEvent)
    assert events[2].status is AlertStatus.ACKNOWLEDGED


def test_get_alert_history_wraps_request_exceptions() -> None:
    """Raise RuntimeError when alert history retrieval fails.

    Returns
    -------
    None
        Assertions fail if error mapping changes.
    """
    client = DatabaseApiClient(base_url="http://localhost:5001")

    with patch("requests.get", side_effect=requests.RequestException("boom")):
        with pytest.raises(RuntimeError, match="Failed to fetch alert history"):
            client.get_alert_history(AlertHistoryQuery(plant_id=1))


def test_get_active_alerts_includes_query_params() -> None:
    """Send query params when requesting active alerts.

    Returns
    -------
    None
        Assertions fail if request parameters regress.
    """
    client = DatabaseApiClient(base_url="http://localhost:5001")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = []
    mock_response.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_response) as mock_get:
        alerts = client.get_active_alerts(ActiveAlertsQuery(plant_id=1))

    assert alerts == []
    mock_get.assert_called_once_with(
        "http://localhost:5001/alerts/active",
        params={"plant_id": 1},
        headers={"Content-Type": "application/json"},
        timeout=10,
    )


def test_ensure_alert_definition_posts_payload() -> None:
    """Upsert alert definition via HTTP POST.

    Returns
    -------
    None
        Assertions fail if request parameters or serialization regress.
    """
    client = DatabaseApiClient(base_url="http://localhost:5001")
    definition = AlertDefinition(
        alert_key="temp_high:sensor_1",
        plant_id=1,
        sensor_id=7,
        source="temperature",
        rule_id="temp_high",
        rule_name="High Temperature",
        kind="sensor",
        persistence_count=3,
        cooldown_seconds=300,
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None

    with patch("requests.post", return_value=mock_response) as mock_post:
        client.ensure_alert_definition(definition)

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "http://localhost:5001/alerts/definitions"
    assert kwargs["headers"] == {"Content-Type": "application/json"}
    assert kwargs["timeout"] == 5
    assert kwargs["json"]["kind"] == "sensor"


def test_ensure_alert_definition_wraps_request_exceptions() -> None:
    """Raise RuntimeError when upserting alert definition fails.

    Returns
    -------
    None
        Assertions fail if error mapping changes.
    """
    client = DatabaseApiClient(base_url="http://localhost:5001")
    definition = AlertDefinition(
        alert_key="temp_high:sensor_1",
        plant_id=1,
        sensor_id=7,
        source="temperature",
        rule_id="temp_high",
        rule_name="High Temperature",
        kind="sensor",
        persistence_count=3,
        cooldown_seconds=300,
    )

    with patch("requests.post", side_effect=requests.RequestException("boom")):
        with pytest.raises(RuntimeError, match="Failed to upsert alert definition"):
            client.ensure_alert_definition(definition)
