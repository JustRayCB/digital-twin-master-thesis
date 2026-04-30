import pytest

from dt.analytics.alerts.rules import SeverityLevel
from dt.communication.adapters import dump, load
from dt.communication.dataclasses.alerts.alert_record import (
    AlertDefinition,
    AlertHistoryEvent,
    AlertStatus,
    ExternalAlertEvent,
    SensorAlertEvent,
)
from dt.communication.dataclasses.alerts.alert_type import AlertType
from dt.communication.topics import Topics


def test_alert_status_values_and_coercion() -> None:
    """Coerce alert statuses from strings and reject unknown values.

    Returns
    -------
    None
        Assertions fail if lifecycle strings change.
    """
    assert AlertStatus.ACTIVE == "active"
    assert AlertStatus.IGNORED == "ignored"
    assert AlertStatus.ACKNOWLEDGED == "acknowledged"
    assert AlertStatus.CLEARED == "cleared"

    assert AlertStatus("active") == AlertStatus.ACTIVE
    assert AlertStatus("ignored") == AlertStatus.IGNORED
    assert AlertStatus("acknowledged") == AlertStatus.ACKNOWLEDGED
    assert AlertStatus("cleared") == AlertStatus.CLEARED

    with pytest.raises(ValueError):
        AlertStatus("invalid_status")


def test_alert_definition_loads_enums_from_dict() -> None:
    """Load AlertDefinition from JSON-safe dict with enum coercion.

    Returns
    -------
    None
        Assertions fail if enum coercion or serialized shapes regress.
    """
    decoded = load(
        "generic",
        AlertDefinition,
        {
            "alert_key": "temp_high:sensor_1",
            "plant_id": 10,
            "sensor_id": 1,
            "source": "temperature",
            "rule_id": "temp_high",
            "rule_name": "High Temperature Alert",
            "kind": "sensor",
            "persistence_count": 3,
            "cooldown_seconds": 300,
        },
    )

    assert decoded.kind is AlertType.SENSOR
    assert decoded.plant_id == 10
    assert decoded.sensor_id == 1

    encoded = dump("generic", decoded)
    assert encoded["kind"] == "sensor"


def test_alert_history_event_loads_severity_and_status_enums() -> None:
    """Load base history events with status and severity enums.

    Returns
    -------
    None
        Assertions fail if enum coercion changes.
    """
    decoded = load(
        "generic",
        AlertHistoryEvent,
        {
            "alert_key": "alert.key",
            "plant_id": 1,
            "timestamp": 123.0,
            "status": "active",
            "severity": "warning",
            "message": "Something happened",
            "correlation_id": "corr-1",
        },
    )

    assert decoded.status is AlertStatus.ACTIVE
    assert decoded.severity is SeverityLevel.WARNING


def test_sensor_alert_event_roundtrips_with_processed_reading() -> None:
    """Round-trip sensor alerts including nested processed readings.

    Returns
    -------
    None
        Assertions fail if nested dataclass serialization regresses.
    """
    payload = {
        "alert_key": "temp_high:sensor_1",
        "plant_id": 10,
        "timestamp": 1234567890.0,
        "status": "active",
        "severity": "critical",
        "message": "Temperature exceeded threshold",
        "correlation_id": "corr-456",
        "reading": {
            "timestamp": 1234567890.0,
            "sensor_id": 1,
            "plant_id": 10,
            "topic": Topics.TEMPERATURE.value,
            "value": 35.0,
            "unit": "C",
            "correlation_id": "corr-456",
            "flags": {"range_violation": False, "valid_data_point": True},
            "dq_score": 0.85,
            "imputed": False,
        },
        "threshold_op": ">",
        "threshold_value": 30.0,
    }

    decoded = load("generic", SensorAlertEvent, payload)
    assert decoded.status is AlertStatus.ACTIVE
    assert decoded.severity is SeverityLevel.CRITICAL
    assert decoded.reading.topic is Topics.TEMPERATURE
    assert decoded.threshold_op == ">"
    assert decoded.threshold_value == 30.0

    encoded = dump("generic", decoded)
    assert encoded["status"] == "active"
    assert encoded["severity"] == "critical"
    assert encoded["reading"]["topic"] == Topics.TEMPERATURE.value


def test_external_alert_event_roundtrips_with_metadata() -> None:
    """Round-trip external alerts including metadata payload.

    Returns
    -------
    None
        Assertions fail if metadata serialization regresses.
    """
    payload = {
        "alert_key": "ai_anomaly",
        "plant_id": 10,
        "timestamp": 1234567890.0,
        "status": "active",
        "severity": "warning",
        "message": "Anomaly detected by AI module",
        "correlation_id": "corr-999",
        "metadata": {"model_version": "v1.2", "confidence": "0.85"},
    }

    decoded = load("generic", ExternalAlertEvent, payload)
    assert decoded.metadata["model_version"] == "v1.2"
    assert decoded.status is AlertStatus.ACTIVE
    assert decoded.severity is SeverityLevel.WARNING

    encoded = dump("generic", decoded)
    assert encoded["metadata"]["confidence"] == "0.85"
