"""Integration tests for the database service REST API."""

import pytest
from sqlalchemy import text

from dt.alerts.rules import SeverityLevel
from dt.communication.adapters import dump, load
from dt.communication.dataclasses import CameraSnapshot, ProcessedSensorData, SensorDescriptor
from dt.communication.dataclasses.alerts.alert_record import (
    AlertDefinition,
    AlertHistoryEvent,
    AlertStatus,
    ExternalAlertEvent,
    SensorAlertEvent,
)
from dt.communication.dataclasses.alerts.alert_type import AlertType
from dt.communication.dataclasses.queries import ActiveAlertsQuery, AlertHistoryQuery, ReadingsQuery
from dt.communication.topics import Topics
from dt.data.database.timescale_storage import TimescaleStorage

pytestmark = [pytest.mark.requires_timescale]


def load_alert_event(payload: dict) -> AlertHistoryEvent:
    """Deserialize alert payloads into alert event types.

    Parameters
    ----------
    payload : dict
        Serialized alert payload returned by the database API.

    Returns
    -------
    AlertHistoryEvent
        Structured alert event instance.
    """
    if "reading" in payload:
        return load("generic", SensorAlertEvent, payload)
    if "metadata" in payload:
        return load("generic", ExternalAlertEvent, payload)
    return load("generic", AlertHistoryEvent, payload)


def test_list_sensors_returns_registered_sensors(client, sample_sensor) -> None:
    """List sensors returns relational sensor metadata.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask client bound to the database API.
    sample_sensor : SensorDescriptor
        Registered sensor descriptor.

    Returns
    -------
    None
        The assertions raise if /sensors output regresses.
    """
    response = client.get("/sensors")

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)
    sensors = [load("generic", SensorDescriptor, item) for item in payload]

    assert any(sensor.id == sample_sensor.id for sensor in sensors)


def test_bind_sensor_persists_to_database(
    client, sample_plant_id: int, storage: TimescaleStorage
) -> None:
    """Bind sensor endpoint registers a sensor and returns the assigned ID.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask client bound to the database API.
    sample_plant_id : int
        Plant identifier to bind the sensor to.
    storage : TimescaleStorage
        Storage used to validate persistence.

    Returns
    -------
    None
        The assertions raise if /bind_sensor regresses.
    """
    sensor = SensorDescriptor(
        id=0,
        plant_id=sample_plant_id,
        name="new_sensor",
        pin=5,
        read_interval=120,
    )
    response = client.post("/bind_sensor", json=dump("generic", sensor))

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, dict)
    sensor_id = payload["sensor_id"]
    assert sensor_id > 0

    sensors = storage.list_sensors()
    assert any(sensor.id == sensor_id and sensor.name == "new_sensor" for sensor in sensors)


def test_bind_sensor_rejects_invalid_json(client) -> None:
    """Bind sensor endpoint rejects invalid JSON payloads.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask client bound to the database API.

    Returns
    -------
    None
        The assertions raise if /bind_sensor error handling regresses.
    """
    response = client.post("/bind_sensor", data="not json", content_type="application/json")

    assert response.status_code == 400
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "error" in payload


def test_get_readings_returns_raw_data(client, storage: TimescaleStorage, sample_sensor) -> None:
    """Readings endpoint returns persisted readings for a sensor.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask client bound to the database API.
    storage : TimescaleStorage
        Storage used to seed readings.
    sample_sensor : SensorDescriptor
        Registered sensor descriptor.

    Returns
    -------
    None
        The assertions raise if /readings raw query regresses.
    """
    storage.ingest_reading(
        ProcessedSensorData(
            plant_id=sample_sensor.plant_id,
            sensor_id=sample_sensor.id,
            timestamp=1234567890.0,
            value=25.5,
            unit="°C",
            topic=Topics.TEMPERATURE,
            correlation_id="test-123",
            flags={},
            dq_score=0.98,
            imputed=False,
        )
    )

    query = ReadingsQuery(window="raw", sensor_id=sample_sensor.id)
    response = client.get("/readings", query_string=dump("generic", query))

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)

    readings = [load("generic", ProcessedSensorData, item) for item in payload]
    assert readings
    assert any(reading.correlation_id == "test-123" for reading in readings)


def test_get_readings_rejects_invalid_query_params(client) -> None:
    """Readings endpoint rejects invalid query parameters.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask client bound to the database API.

    Returns
    -------
    None
        The assertions raise if /readings parameter validation regresses.
    """
    response = client.get("/readings", query_string={"since": "not-a-float"})

    assert response.status_code == 400
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "error" in payload


def test_get_latest_camera_snapshot_returns_404_when_absent(client) -> None:
    """Latest snapshot endpoint returns 404 when no snapshot is available."""
    response = client.get("/camera/snapshots/latest", query_string={"plant_id": 1})

    assert response.status_code == 404
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "error" in payload


def test_get_latest_camera_snapshot_returns_camera_payload(
    client, storage: TimescaleStorage, sample_sensor: SensorDescriptor
) -> None:
    """Latest snapshot endpoint returns persisted camera payload in API shape."""
    snapshot = CameraSnapshot(
        plant_id=sample_sensor.plant_id,
        sensor_id=sample_sensor.id,
        timestamp=1234567890.0,
        topic=Topics.CAMERA_IMAGE,
        correlation_id="camera-123",
        mime_type="image/jpeg",
        image="AQI=",
        width=640,
        height=480,
    )
    storage.ingest_camera_snapshot(snapshot)

    response = client.get(
        "/camera/snapshots/latest",
        query_string={"plant_id": sample_sensor.plant_id},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert load("generic", CameraSnapshot, payload) == snapshot


def test_list_actuators_returns_persisted_actuators(
    client, storage: TimescaleStorage, sample_plant_id: int
) -> None:
    """List actuators returns stored actuators.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask client bound to the database API.
    storage : TimescaleStorage
        Storage used to seed actuator records.
    sample_plant_id : int
        Plant identifier owning the actuator.

    Returns
    -------
    None
        The assertions raise if /actuators output regresses.
    """
    actuator_id = storage.register_actuator(sample_plant_id, "water_pump", 17, 0)

    response = client.get("/actuators")

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)
    assert any(actuator["id"] == actuator_id for actuator in payload)


def test_get_alert_history_returns_persisted_events(
    client, storage: TimescaleStorage, sample_sensor
) -> None:
    """Alert history endpoint returns persisted alert events.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask client bound to the database API.
    storage : TimescaleStorage
        Storage used to seed alerts.
    sample_sensor : SensorDescriptor
        Registered sensor descriptor used by the alert.

    Returns
    -------
    None
        The assertions raise if /alerts/history regresses.
    """
    definition = AlertDefinition(
        alert_key="high_temp:temperature",
        plant_id=sample_sensor.plant_id,
        sensor_id=sample_sensor.id,
        source="temperature",
        rule_id="rule-1",
        rule_name="high_temp",
        kind=AlertType.SENSOR,
        persistence_count=3,
        cooldown_seconds=300,
    )
    storage.save_alert_definition(definition)

    event = SensorAlertEvent(
        alert_key=definition.alert_key,
        plant_id=definition.plant_id,
        timestamp=1234567890.0,
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.WARNING,
        message="Temperature exceeds threshold",
        correlation_id="alert-123",
        reading=ProcessedSensorData(
            plant_id=sample_sensor.plant_id,
            sensor_id=sample_sensor.id,
            timestamp=1234567890.0,
            value=35.0,
            unit="°C",
            topic=Topics.TEMPERATURE,
            correlation_id="alert-123",
            flags={},
            dq_score=1.0,
            imputed=False,
        ),
        threshold_op=">",
        threshold_value=30.0,
    )
    storage.save_alert_event(event)

    response = client.get("/alerts/history", query_string=dump("generic", AlertHistoryQuery()))

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)

    events = [load_alert_event(item) for item in payload]
    assert any(event.correlation_id == "alert-123" for event in events)


def test_get_active_alerts_excludes_cleared_events(
    client, storage: TimescaleStorage, sample_sensor
) -> None:
    """Active alerts endpoint excludes cleared alerts.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask client bound to the database API.
    storage : TimescaleStorage
        Storage used to seed alerts.
    sample_sensor : SensorDescriptor
        Registered sensor descriptor used by the alert.

    Returns
    -------
    None
        The assertions raise if /alerts/active regresses.
    """
    definition = AlertDefinition(
        alert_key="active:temp",
        plant_id=sample_sensor.plant_id,
        sensor_id=sample_sensor.id,
        source="temperature",
        rule_id="rule-active",
        rule_name="active_temp",
        kind=AlertType.SENSOR,
        persistence_count=1,
        cooldown_seconds=300,
    )
    storage.save_alert_definition(definition)

    storage.save_alert_event(
        SensorAlertEvent(
            alert_key=definition.alert_key,
            plant_id=definition.plant_id,
            timestamp=1234567890.0,
            status=AlertStatus.ACTIVE,
            severity=SeverityLevel.WARNING,
            message="Active alert",
            correlation_id="corr-active",
            reading=ProcessedSensorData(
                plant_id=sample_sensor.plant_id,
                sensor_id=sample_sensor.id,
                timestamp=1234567890.0,
                value=35.0,
                unit="°C",
                topic=Topics.TEMPERATURE,
                correlation_id="corr-active",
                flags={},
                dq_score=1.0,
                imputed=False,
            ),
            threshold_op=">",
            threshold_value=30.0,
        )
    )

    storage.save_alert_event(
        SensorAlertEvent(
            alert_key=definition.alert_key,
            plant_id=definition.plant_id,
            timestamp=1234567891.0,
            status=AlertStatus.CLEARED,
            severity=SeverityLevel.WARNING,
            message="Cleared alert",
            correlation_id="corr-cleared",
            reading=ProcessedSensorData(
                plant_id=sample_sensor.plant_id,
                sensor_id=sample_sensor.id,
                timestamp=1234567891.0,
                value=33.0,
                unit="°C",
                topic=Topics.TEMPERATURE,
                correlation_id="corr-cleared",
                flags={},
                dq_score=1.0,
                imputed=False,
            ),
            threshold_op=">",
            threshold_value=30.0,
            cleared_ts=1234567891.0,
        )
    )

    response = client.get("/alerts/active", query_string=dump("generic", ActiveAlertsQuery()))

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, list)

    events = [load_alert_event(item) for item in payload]
    assert all(event.status != AlertStatus.CLEARED for event in events)


def test_ensure_alert_definition_is_idempotent(
    client, storage: TimescaleStorage, sample_sensor
) -> None:
    """Ensure alert definition endpoint upserts without duplication.

    Parameters
    ----------
    client : flask.testing.FlaskClient
        Flask client bound to the database API.
    storage : TimescaleStorage
        Storage used to validate persistence.
    sample_sensor : SensorDescriptor
        Registered sensor descriptor used by the definition.

    Returns
    -------
    None
        The assertions raise if /alerts/definitions regresses.
    """
    definition = AlertDefinition(
        alert_key="high_temp:temperature",
        plant_id=sample_sensor.plant_id,
        sensor_id=sample_sensor.id,
        source="temperature",
        rule_id="rule-1",
        rule_name="high_temp",
        kind=AlertType.SENSOR,
        persistence_count=3,
        cooldown_seconds=300,
    )

    payload = dump("generic", definition)
    first = client.post("/alerts/definitions", json=payload)
    second = client.post("/alerts/definitions", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200

    with storage.engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT COUNT(*) FROM alert_definitions WHERE alert_key = :key AND plant_id = :plant_id"
            ),
            {"key": definition.alert_key, "plant_id": definition.plant_id},
        ).scalar_one()
    assert rows == 1
