"""Integration tests for the TimescaleStorage implementation."""

import time
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from dt.alerts.rules import SeverityLevel
from dt.communication.dataclasses import (CameraSnapshot, ProcessedSensorData,
                                          SensorDescriptor)
from dt.communication.dataclasses.alerts.alert_record import (
    AlertDefinition, AlertHistoryEvent, AlertStatus, ExternalAlertEvent,
    SensorAlertEvent)
from dt.communication.dataclasses.alerts.alert_type import AlertType
from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.dataclasses.queries import (ActiveAlertsQuery,
                                                  AlertHistoryQuery,
                                                  ReadingsQuery)
from dt.communication.topics import Topics
from dt.data.database.timescale_storage import TimescaleStorage

pytestmark = [pytest.mark.requires_timescale]


def test_upsert_plant_inserts_row(test_storage: TimescaleStorage) -> None:
    """Insert a plant record and return its identifier.

    Parameters
    ----------
    test_storage : TimescaleStorage
        Storage instance backed by the test database.

    Returns
    -------
    None
        The assertions raise if plant insertion regresses.
    """
    plant_id = test_storage.upsert_plant(name="Tomato Plant", notes="Test plant")

    assert plant_id > 0
    plants = test_storage.list_plants()
    assert plants == [{"id": plant_id, "name": "Tomato Plant", "notes": "Test plant"}]


def test_upsert_plant_updates_existing_row(test_storage: TimescaleStorage) -> None:
    """Update an existing plant record in place.

    Parameters
    ----------
    test_storage : TimescaleStorage
        Storage instance backed by the test database.

    Returns
    -------
    None
        The assertions raise if updating a plant regresses.
    """
    plant_id = test_storage.upsert_plant(name="Tomato Plant", notes="Initial notes")
    updated_id = test_storage.upsert_plant(
        plant_id=plant_id, name="Updated Tomato", notes="Updated notes"
    )

    assert updated_id == plant_id
    plants = test_storage.list_plants()
    assert plants[0]["name"] == "Updated Tomato"
    assert plants[0]["notes"] == "Updated notes"


def test_register_and_list_sensors(test_storage: TimescaleStorage) -> None:
    """Register sensors and list them back.

    Parameters
    ----------
    test_storage : TimescaleStorage
        Storage instance backed by the test database.

    Returns
    -------
    None
        The assertions raise if sensor persistence regresses.
    """
    plant_id = test_storage.upsert_plant(name="Test Plant")

    sensor1 = SensorDescriptor(id=-1, plant_id=plant_id, name="DHT22", pin=4, read_interval=120)
    sensor2 = SensorDescriptor(id=-1, plant_id=plant_id, name="BH1750", pin=5, read_interval=60)

    id1 = test_storage.register_sensor(sensor1)
    id2 = test_storage.register_sensor(sensor2)

    sensors = test_storage.list_sensors()
    assert [sensor.id for sensor in sensors] == [id1, id2]
    assert [sensor.name for sensor in sensors] == ["DHT22", "BH1750"]


def test_register_sensor_rejects_unknown_plant(test_storage: TimescaleStorage) -> None:
    """Reject sensor registration when the plant foreign key is missing.

    Parameters
    ----------
    test_storage : TimescaleStorage
        Storage instance backed by the test database.

    Returns
    -------
    None
        The assertions raise if FK enforcement regresses.
    """
    sensor = SensorDescriptor(
        id=-1,
        plant_id=9999,
        name="DHT22",
        pin=4,
        read_interval=120,
    )

    with pytest.raises(IntegrityError):
        test_storage.register_sensor(sensor)


def test_register_and_list_actuators(test_storage: TimescaleStorage) -> None:
    """Register actuators and list them back.

    Parameters
    ----------
    test_storage : TimescaleStorage
        Storage instance backed by the test database.

    Returns
    -------
    None
        The assertions raise if actuator persistence regresses.
    """
    plant_id = test_storage.upsert_plant(name="Test Plant")
    test_storage.register_actuator(plant_id, "Water Pump", 17, 1)
    test_storage.register_actuator(plant_id, "Light", 18, 2)

    actuators = test_storage.list_actuators()
    assert [actuator["name"] for actuator in actuators] == ["Water Pump", "Light"]
    assert [actuator["pin"] for actuator in actuators] == [17, 18]
    assert [actuator["relay_channel"] for actuator in actuators] == [1, 2]


def test_ingest_reading_persists_and_can_query_raw(test_storage: TimescaleStorage) -> None:
    """Persist a processed reading and retrieve it by query filters.

    Parameters
    ----------
    test_storage : TimescaleStorage
        Storage instance backed by the test database.

    Returns
    -------
    None
        The assertions raise if ingest/query regresses.
    """
    plant_id = test_storage.upsert_plant(name="Test Plant")
    sensor_id = test_storage.register_sensor(
        SensorDescriptor(id=-1, plant_id=plant_id, name="DHT22", pin=4, read_interval=120)
    )

    now = time.time()
    reading = ProcessedSensorData(
        plant_id=plant_id,
        sensor_id=sensor_id,
        timestamp=now,
        value=22.5,
        unit="°C",
        topic=Topics.TEMPERATURE,
        correlation_id="test-corr-1",
        flags={ValidationFlag.VALID: True},
        dq_score=1.0,
        imputed=False,
        raw_value=22.3,
        calibrated_value=22.4,
        normalized_value=0.75,
        calibration_profile_id="default",
        normalization_profile_id="temp_norm",
    )
    test_storage.ingest_reading(reading)

    readings = test_storage.query_readings(
        ReadingsQuery(sensor_id=sensor_id, since=now - 60, until=now + 60, window="raw")
    )

    assert len(readings) == 1
    assert readings[0].correlation_id == "test-corr-1"
    assert readings[0].value == 22.5
    assert readings[0].raw_value == 22.3


def test_ingest_reading_rejects_unknown_sensor(test_storage: TimescaleStorage) -> None:
    """Reject reading ingest when the sensor foreign key is missing.

    Parameters
    ----------
    test_storage : TimescaleStorage
        Storage instance backed by the test database.

    Returns
    -------
    None
        The assertions raise if FK enforcement regresses.
    """
    plant_id = test_storage.upsert_plant(name="Test Plant")
    reading = ProcessedSensorData(
        plant_id=plant_id,
        sensor_id=9999,
        timestamp=time.time(),
        value=22.5,
        unit="°C",
        topic=Topics.TEMPERATURE,
        correlation_id="test-corr-unknown-sensor",
        flags={ValidationFlag.VALID: True},
        dq_score=1.0,
        imputed=False,
    )

    with pytest.raises(IntegrityError):
        test_storage.ingest_reading(reading)


def test_query_aggregates_returns_1h_buckets(test_storage: TimescaleStorage) -> None:
    """Aggregate readings into 1-hour buckets via the continuous aggregate.

    Parameters
    ----------
    test_storage : TimescaleStorage
        Storage instance backed by the test database.

    Returns
    -------
    None
        The assertions raise if aggregate queries regress.
    """
    plant_id = test_storage.upsert_plant(name="Test Plant")
    sensor_id = test_storage.register_sensor(
        SensorDescriptor(id=-1, plant_id=plant_id, name="DHT22", pin=4, read_interval=120)
    )

    base_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp()
    for i in range(6):
        test_storage.ingest_reading(
            ProcessedSensorData(
                plant_id=plant_id,
                sensor_id=sensor_id,
                timestamp=base_time + i * 600,
                value=20.0 + i,
                unit="°C",
                topic=Topics.TEMPERATURE,
                correlation_id=f"agg-corr-{i}",
                flags={ValidationFlag.VALID: True},
                dq_score=1.0,
                imputed=False,
            )
        )

    with test_storage.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("CALL refresh_continuous_aggregate('sensor_readings_1h', NULL, NULL);"))
        conn.commit()

    aggregates = test_storage.query_aggregates(
        ReadingsQuery(
            sensor_id=sensor_id, since=base_time - 60, until=base_time + 7200, window="1h"
        )
    )

    assert aggregates
    assert aggregates[0].avg_value == 22.5
    assert aggregates[0].min_value == 20.0
    assert aggregates[0].max_value == 25.0


def test_save_alert_event_requires_registered_definition(test_storage: TimescaleStorage) -> None:
    """Fail fast when saving an event without a pre-registered definition.

    Parameters
    ----------
    test_storage : TimescaleStorage
        Storage instance backed by the test database.

    Returns
    -------
    None
        The assertions raise if alert definition enforcement regresses.
    """
    plant_id = test_storage.upsert_plant(name="Test Plant")
    event = AlertHistoryEvent(
        alert_key="missing:def",
        plant_id=plant_id,
        timestamp=time.time(),
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.WARNING,
        message="Too hot!",
        correlation_id="corr-missing-def",
    )

    with pytest.raises(ValueError, match="alert definition"):
        test_storage.save_alert_event(event)

    with test_storage.engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM alert_history")).scalar_one() == 0


def test_save_and_load_sensor_alert_event(test_storage: TimescaleStorage) -> None:
    """Persist a sensor alert event and reconstruct it from storage.

    Parameters
    ----------
    test_storage : TimescaleStorage
        Storage instance backed by the test database.

    Returns
    -------
    None
        The assertions raise if alert event persistence regresses.
    """
    plant_id = test_storage.upsert_plant(name="Test Plant")
    sensor_id = test_storage.register_sensor(
        SensorDescriptor(id=-1, plant_id=plant_id, name="DHT22", pin=4, read_interval=120)
    )

    definition = AlertDefinition(
        alert_key="high_temp:temperature",
        plant_id=plant_id,
        sensor_id=sensor_id,
        source="temperature",
        rule_id="rule-1",
        rule_name="High Temperature",
        kind=AlertType.SENSOR,
        persistence_count=1,
        cooldown_seconds=300,
    )
    test_storage.save_alert_definition(definition)

    reading = ProcessedSensorData(
        plant_id=plant_id,
        sensor_id=sensor_id,
        timestamp=time.time(),
        value=35.0,
        unit="°C",
        topic=Topics.TEMPERATURE,
        correlation_id="corr-1",
        flags={ValidationFlag.VALID: True},
        dq_score=1.0,
        imputed=False,
    )
    event = SensorAlertEvent(
        alert_key=definition.alert_key,
        plant_id=plant_id,
        timestamp=time.time(),
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.WARNING,
        message="Too hot!",
        correlation_id="corr-1",
        reading=reading,
        threshold_op=">",
        threshold_value=30.0,
    )

    event_id = test_storage.save_alert_event(event)
    assert event_id > 0

    history = test_storage.get_alert_history(AlertHistoryQuery(plant_id=plant_id))
    assert len(history) == 1
    saved_event = history[0]

    assert isinstance(saved_event, SensorAlertEvent)
    assert saved_event.reading.value == 35.0
    assert saved_event.threshold_op == ">"


def test_save_and_load_external_alert_event(test_storage: TimescaleStorage) -> None:
    """Persist an external alert event and reconstruct it from storage.

    Parameters
    ----------
    test_storage : TimescaleStorage
        Storage instance backed by the test database.

    Returns
    -------
    None
        The assertions raise if external alert persistence regresses.
    """
    plant_id = test_storage.upsert_plant(name="Test Plant")
    definition = AlertDefinition(
        alert_key="weather:storm",
        plant_id=plant_id,
        sensor_id=None,
        source="weather_api",
        rule_id=None,
        rule_name="Storm Warning",
        kind=AlertType.EXTERNAL,
        persistence_count=0,
        cooldown_seconds=0,
    )
    test_storage.save_alert_definition(definition)

    event = ExternalAlertEvent(
        alert_key=definition.alert_key,
        plant_id=plant_id,
        timestamp=time.time(),
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.CRITICAL,
        message="Storm approaching",
        correlation_id="corr-ext-1",
        metadata={"wind_speed": "100km/h", "direction": "NW"},
    )

    test_storage.save_alert_event(event)
    history = test_storage.get_alert_history(AlertHistoryQuery(plant_id=plant_id))

    assert len(history) == 1
    saved_event = history[0]
    assert isinstance(saved_event, ExternalAlertEvent)
    assert saved_event.metadata["wind_speed"] == "100km/h"


def test_sensor_alert_details_reject_duplicate_rows(test_storage: TimescaleStorage) -> None:
    """Enforce one sensor detail row per alert_history event."""
    plant_id = test_storage.upsert_plant(name="Test Plant")
    sensor_id = test_storage.register_sensor(
        SensorDescriptor(id=-1, plant_id=plant_id, name="DHT22", pin=4, read_interval=120)
    )

    definition = AlertDefinition(
        alert_key="high_temp:temperature",
        plant_id=plant_id,
        sensor_id=sensor_id,
        source="temperature",
        rule_id="rule-1",
        rule_name="High Temperature",
        kind=AlertType.SENSOR,
        persistence_count=1,
        cooldown_seconds=300,
    )
    test_storage.save_alert_definition(definition)

    reading = ProcessedSensorData(
        plant_id=plant_id,
        sensor_id=sensor_id,
        timestamp=time.time(),
        value=35.0,
        unit="°C",
        topic=Topics.TEMPERATURE,
        correlation_id="corr-dup-sensor-1",
        flags={ValidationFlag.VALID: True},
        dq_score=1.0,
        imputed=False,
    )
    event = SensorAlertEvent(
        alert_key=definition.alert_key,
        plant_id=plant_id,
        timestamp=time.time(),
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.WARNING,
        message="Too hot!",
        correlation_id="corr-dup-sensor-1",
        reading=reading,
        threshold_op=">",
        threshold_value=30.0,
    )

    event_id = test_storage.save_alert_event(event)

    duplicate_query = """
        INSERT INTO alert_sensors (
            alert_history_id, sensor_id, plant_id, timestamp,
            value, unit, topic, correlation_id,
            flags, dq_score, imputed,
            raw_value, calibrated_value, normalized_value,
            calibration_profile_id, normalization_profile_id,
            threshold_op, threshold_value, range_min, range_max
        )
        SELECT
            alert_history_id, sensor_id, plant_id, timestamp,
            value, unit, topic, correlation_id,
            flags, dq_score, imputed,
            raw_value, calibrated_value, normalized_value,
            calibration_profile_id, normalization_profile_id,
            threshold_op, threshold_value, range_min, range_max
        FROM alert_sensors
        WHERE alert_history_id = :alert_history_id AND plant_id = :plant_id
    """
    with test_storage.engine.begin() as conn, pytest.raises(IntegrityError):
        conn.execute(
            text(duplicate_query),
            {"alert_history_id": event_id, "plant_id": plant_id},
        )


def test_external_alert_details_reject_duplicate_rows(test_storage: TimescaleStorage) -> None:
    """Enforce one external detail row per alert_history event."""
    plant_id = test_storage.upsert_plant(name="Test Plant")
    definition = AlertDefinition(
        alert_key="weather:storm",
        plant_id=plant_id,
        sensor_id=None,
        source="weather_api",
        rule_id=None,
        rule_name="Storm Warning",
        kind=AlertType.EXTERNAL,
        persistence_count=0,
        cooldown_seconds=0,
    )
    test_storage.save_alert_definition(definition)

    event = ExternalAlertEvent(
        alert_key=definition.alert_key,
        plant_id=plant_id,
        timestamp=time.time(),
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.CRITICAL,
        message="Storm approaching",
        correlation_id="corr-dup-ext-1",
        metadata={"wind_speed": "100km/h", "direction": "NW"},
    )

    event_id = test_storage.save_alert_event(event)

    duplicate_query = """
        INSERT INTO alert_external (alert_history_id, plant_id, metadata)
        SELECT alert_history_id, plant_id, metadata
        FROM alert_external
        WHERE alert_history_id = :alert_history_id AND plant_id = :plant_id
    """
    with test_storage.engine.begin() as conn, pytest.raises(IntegrityError):
        conn.execute(
            text(duplicate_query),
            {"alert_history_id": event_id, "plant_id": plant_id},
        )


def test_get_active_alerts_excludes_cleared(test_storage: TimescaleStorage) -> None:
    """Exclude cleared alerts from the active alerts response.

    Parameters
    ----------
    test_storage : TimescaleStorage
        Storage instance backed by the test database.

    Returns
    -------
    None
        The assertions raise if active alert selection regresses.
    """
    plant_id = test_storage.upsert_plant(name="Test Plant")
    definition = AlertDefinition(
        alert_key="high_temp:temperature",
        plant_id=plant_id,
        sensor_id=None,
        source="temperature",
        rule_id="rule-1",
        rule_name="High Temperature",
        kind=AlertType.SENSOR,
        persistence_count=3,
        cooldown_seconds=300,
    )
    test_storage.save_alert_definition(definition)

    test_storage.save_alert_event(
        AlertHistoryEvent(
            alert_key=definition.alert_key,
            plant_id=plant_id,
            timestamp=time.time(),
            status=AlertStatus.ACTIVE,
            severity=SeverityLevel.WARNING,
            message="Too hot!",
            correlation_id="corr-1",
        )
    )
    active = test_storage.get_active_alerts(ActiveAlertsQuery(plant_id=plant_id))
    assert len(active) == 1

    test_storage.save_alert_event(
        AlertHistoryEvent(
            alert_key=definition.alert_key,
            plant_id=plant_id,
            timestamp=time.time() + 5,
            status=AlertStatus.CLEARED,
            severity=SeverityLevel.WARNING,
            message="Back to normal",
            correlation_id="corr-2",
            cleared_ts=time.time() + 5,
        )
    )
    active = test_storage.get_active_alerts(ActiveAlertsQuery(plant_id=plant_id))
    assert active == []


def test_ingest_camera_snapshot_and_get_latest_returns_newest(
    test_storage: TimescaleStorage,
) -> None:
    """Persist camera snapshots and return the latest snapshot for the plant/topic."""
    plant_id = test_storage.upsert_plant(name="Camera Plant")
    sensor_id = test_storage.register_sensor(
        SensorDescriptor(id=-1, plant_id=plant_id, name="Camera", pin=-1, read_interval=60)
    )

    older = CameraSnapshot(
        plant_id=plant_id,
        sensor_id=sensor_id,
        timestamp=1_735_689_600.0,
        topic=Topics.CAMERA_IMAGE,
        correlation_id="camera-older",
        mime_type="image/jpeg",
        image="AQI=",
        width=640,
        height=480,
    )
    newer = CameraSnapshot(
        plant_id=plant_id,
        sensor_id=sensor_id,
        timestamp=1_735_689_700.0,
        topic=Topics.CAMERA_IMAGE,
        correlation_id="camera-newer",
        mime_type="image/jpeg",
        image="AQM=",
        width=640,
        height=480,
    )

    first_id = test_storage.ingest_camera_snapshot(older)
    second_id = test_storage.ingest_camera_snapshot(newer)

    assert first_id > 0
    assert second_id > first_id

    latest = test_storage.get_latest_camera_snapshot(plant_id=plant_id)

    assert latest is not None
    assert latest.correlation_id == "camera-newer"
    assert latest.image == "AQM="
    assert latest.topic is Topics.CAMERA_IMAGE
    assert latest.width == 640
    assert latest.height == 480


def test_get_latest_camera_snapshot_filters_by_plant_and_topic(test_storage: TimescaleStorage) -> None:
    """Filter latest camera snapshot by requested plant and topic."""
    plant_one = test_storage.upsert_plant(name="Plant One")
    plant_two = test_storage.upsert_plant(name="Plant Two")
    sensor_one = test_storage.register_sensor(
        SensorDescriptor(id=-1, plant_id=plant_one, name="Camera One", pin=-1, read_interval=60)
    )
    sensor_two = test_storage.register_sensor(
        SensorDescriptor(id=-1, plant_id=plant_two, name="Camera Two", pin=-1, read_interval=60)
    )

    test_storage.ingest_camera_snapshot(
        CameraSnapshot(
            plant_id=plant_one,
            sensor_id=sensor_one,
            timestamp=1_735_689_600.0,
            topic=Topics.CAMERA_IMAGE,
            correlation_id="camera-plant-1",
            mime_type="image/jpeg",
            image="AQI=",
            width=640,
            height=480,
        )
    )
    test_storage.ingest_camera_snapshot(
        CameraSnapshot(
            plant_id=plant_two,
            sensor_id=sensor_two,
            timestamp=1_735_689_700.0,
            topic=Topics.CAMERA_IMAGE,
            correlation_id="camera-plant-2",
            mime_type="image/jpeg",
            image="AQM=",
            width=640,
            height=480,
        )
    )

    latest_plant_one = test_storage.get_latest_camera_snapshot(plant_id=plant_one)
    missing_plant = test_storage.get_latest_camera_snapshot(plant_id=999_999)

    assert latest_plant_one is not None
    assert latest_plant_one.correlation_id == "camera-plant-1"
    assert missing_plant is None
