from unittest.mock import MagicMock, patch

from dt.alerts.rules import SeverityLevel
from dt.communication.dataclasses.alerts.alert_record import AlertStatus, ExternalAlertEvent, SensorAlertEvent
from dt.communication.dataclasses.queries import ActiveAlertsQuery
from dt.communication.db_client import DatabaseApiClient
from dt.communication.topics import Topics


def test_get_active_alerts_requests_and_parses_events() -> None:
    """Fetch active alerts and parse polymorphic events from HTTP payload.

    Returns
    -------
    None
        Assertions fail if request parameters or payload parsing regresses.
    """
    client = DatabaseApiClient(base_url="http://localhost:5001")

    sensor_alert_payload = {
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
    }
    external_alert_payload = {
        "alert_key": "ai:anomaly",
        "plant_id": 1,
        "timestamp": 1234567891.0,
        "status": "active",
        "severity": "critical",
        "message": "Anomaly detected",
        "correlation_id": "corr2",
        "metadata": {"model": "demo"},
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [sensor_alert_payload, external_alert_payload]
    mock_response.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_response) as mock_get:
        alerts = client.get_active_alerts(ActiveAlertsQuery(plant_id=1))

    mock_get.assert_called_once_with(
        "http://localhost:5001/alerts/active",
        params={"plant_id": 1},
        headers={"Content-Type": "application/json"},
        timeout=10,
    )

    assert len(alerts) == 2
    assert isinstance(alerts[0], SensorAlertEvent)
    assert alerts[0].alert_key == "rule1:temp"
    assert alerts[0].status is AlertStatus.ACTIVE
    assert alerts[0].severity is SeverityLevel.WARNING
    assert alerts[0].reading.topic is Topics.TEMPERATURE

    assert isinstance(alerts[1], ExternalAlertEvent)
    assert alerts[1].severity is SeverityLevel.CRITICAL
    assert alerts[1].metadata["model"] == "demo"
