"""Integration tests for database persistence stores."""

import time
from base64 import b64decode
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from dt.analytics.alerts.rules import SeverityLevel
from dt.communication.dataclasses.analytics import (
    ActionResult,
    ForecastResult,
    HealthAssessment,
    HealthState,
    Recommendation,
    ModelMetadata,
)
from dt.communication.dataclasses import (
    CameraSnapshot,
    ProcessedSensorData,
    SensorDescriptor,
)
from dt.communication.dataclasses.analytics import RecommendedAction
from dt.communication.dataclasses.alerts.alert_record import (
    AlertDefinition,
    AlertHistoryEvent,
    AlertStatus,
    ExternalAlertEvent,
    SensorAlertEvent,
)
from dt.communication.dataclasses.alerts.alert_type import AlertType
from dt.communication.dataclasses.controller import ActionCommand
from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.dataclasses.queries import (
    ActiveAlertsQuery,
    ActionHistoryQuery,
    AlertHistoryQuery,
    CameraSnapshotQuery,
    ForecastHistoryQuery,
    HealthHistoryQuery,
    RecommendationHistoryQuery,
    ReadingsQuery,
)
from dt.communication.topics import Topics
from dt.data.database import AnalyticsStore

pytestmark = [pytest.mark.requires_timescale]


def test_upsert_plant_inserts_row(metadata_store) -> None:
    """Insert a plant record and return its identifier.

    Parameters
    ----------
    metadata_store : MetadataStore
        Store backed by the test database.

    Returns
    -------
    None
        The assertions raise if plant insertion regresses.
    """
    plant_id = metadata_store.upsert_plant(name="Tomato Plant", notes="Test plant")

    assert plant_id > 0
    plants = metadata_store.list_plants()
    assert plants == [{"id": plant_id, "name": "Tomato Plant", "notes": "Test plant"}]


def test_upsert_plant_updates_existing_row(metadata_store) -> None:
    """Update an existing plant record in place.

    Parameters
    ----------
    metadata_store : MetadataStore
        Store backed by the test database.

    Returns
    -------
    None
        The assertions raise if updating a plant regresses.
    """
    plant_id = metadata_store.upsert_plant(name="Tomato Plant", notes="Initial notes")
    updated_id = metadata_store.upsert_plant(
        plant_id=plant_id, name="Updated Tomato", notes="Updated notes"
    )

    assert updated_id == plant_id
    plants = metadata_store.list_plants()
    assert plants[0]["name"] == "Updated Tomato"
    assert plants[0]["notes"] == "Updated notes"


def test_register_and_list_sensors(metadata_store) -> None:
    """Register sensors and list them back.

    Parameters
    ----------
    metadata_store : MetadataStore
        Store backed by the test database.

    Returns
    -------
    None
        The assertions raise if sensor persistence regresses.
    """
    plant_id = metadata_store.upsert_plant(name="Test Plant")

    sensor1 = SensorDescriptor(
        id=-1, plant_id=plant_id, name="DHT22", pin=4, read_interval=120
    )
    sensor2 = SensorDescriptor(
        id=-1, plant_id=plant_id, name="BH1750", pin=5, read_interval=60
    )

    id1 = metadata_store.register_sensor(sensor1)
    id2 = metadata_store.register_sensor(sensor2)

    sensors = metadata_store.list_sensors()
    assert [sensor.id for sensor in sensors] == [id1, id2]
    assert [sensor.name for sensor in sensors] == ["DHT22", "BH1750"]


def test_register_sensor_rejects_unknown_plant(metadata_store) -> None:
    """Reject sensor registration when the plant foreign key is missing.

    Parameters
    ----------
    metadata_store : MetadataStore
        Store backed by the test database.

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
        metadata_store.register_sensor(sensor)


def test_register_and_list_actuators(metadata_store) -> None:
    """Register actuators and list them back.

    Parameters
    ----------
    metadata_store : MetadataStore
        Store backed by the test database.

    Returns
    -------
    None
        The assertions raise if actuator persistence regresses.
    """
    plant_id = metadata_store.upsert_plant(name="Test Plant")
    metadata_store.register_actuator(plant_id, "Water Pump", 17, 1)
    metadata_store.register_actuator(plant_id, "Light", 18, 2)

    actuators = metadata_store.list_actuators()
    assert [actuator["name"] for actuator in actuators] == ["Water Pump", "Light"]
    assert [actuator["pin"] for actuator in actuators] == [17, 18]
    assert [actuator["relay_channel"] for actuator in actuators] == [1, 2]


def test_ingest_reading_persists_and_can_query_raw(
    metadata_store, readings_store
) -> None:
    """Persist a processed reading and retrieve it by query filters.

    Parameters
    ----------
    metadata_store : MetadataStore
        Store used for relational setup.
    readings_store : ReadingsStore
        Store used for time-series persistence.

    Returns
    -------
    None
        The assertions raise if ingest/query regresses.
    """
    plant_id = metadata_store.upsert_plant(name="Test Plant")
    sensor_id = metadata_store.register_sensor(
        SensorDescriptor(
            id=-1, plant_id=plant_id, name="DHT22", pin=4, read_interval=120
        )
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
    readings_store.ingest_reading(reading)

    readings = readings_store.query_readings(
        ReadingsQuery(sensor_id=sensor_id, since=now - 60, until=now + 60, window="raw")
    )

    assert len(readings) == 1
    assert readings[0].correlation_id == "test-corr-1"
    assert readings[0].value == 22.5
    assert readings[0].raw_value == 22.3


def test_ingest_reading_rejects_unknown_sensor(metadata_store, readings_store) -> None:
    """Reject reading ingest when the sensor foreign key is missing.

    Parameters
    ----------
    metadata_store : MetadataStore
        Store used for relational setup.
    readings_store : ReadingsStore
        Store used for time-series persistence.

    Returns
    -------
    None
        The assertions raise if FK enforcement regresses.
    """
    plant_id = metadata_store.upsert_plant(name="Test Plant")
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
        readings_store.ingest_reading(reading)


def test_query_aggregates_returns_1h_buckets(metadata_store, readings_store) -> None:
    """Aggregate readings into 1-hour buckets via the continuous aggregate.

    Parameters
    ----------
    metadata_store : MetadataStore
        Store used for relational setup.
    readings_store : ReadingsStore
        Store used for time-series persistence.

    Returns
    -------
    None
        The assertions raise if aggregate queries regress.
    """
    plant_id = metadata_store.upsert_plant(name="Test Plant")
    sensor_id = metadata_store.register_sensor(
        SensorDescriptor(
            id=-1, plant_id=plant_id, name="DHT22", pin=4, read_interval=120
        )
    )

    base_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp()
    for i in range(6):
        readings_store.ingest_reading(
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

    with readings_store.engine.connect().execution_options(
        isolation_level="AUTOCOMMIT"
    ) as conn:
        conn.execute(
            text("CALL refresh_continuous_aggregate('sensor_readings_1h', NULL, NULL);")
        )
        conn.commit()

    aggregates = readings_store.query_aggregates(
        ReadingsQuery(
            since=base_time - 60,
            until=base_time + 7200,
            window="1h",
        )
    )

    assert aggregates
    assert aggregates[0].mean_value == 22.5
    assert aggregates[0].min_value == 20.0
    assert aggregates[0].max_value == 25.0
    assert aggregates[0].variance_value == pytest.approx(3.5)
    assert aggregates[0].stddev_value == pytest.approx(3.5**0.5)
    assert aggregates[0].skewness_value == pytest.approx(0.0, abs=1e-12)


def test_query_aggregates_reuses_shared_filter_query(
    monkeypatch, readings_store
) -> None:
    """Build aggregate filters via the shared helper with bucket timestamps."""

    seen: dict[str, str] = {}

    def fake_build_filter_query(
        base_query: str,
        query: ReadingsQuery,
        time_col: str,
    ) -> tuple[str, dict[str, float]]:
        seen["time_col"] = time_col
        return f"{base_query}\nORDER BY {time_col} ASC", {}

    monkeypatch.setattr(readings_store, "_build_filter_query", fake_build_filter_query)

    aggregates = readings_store.query_aggregates(ReadingsQuery(window="1h"))

    assert isinstance(aggregates, list)
    assert seen["time_col"] == "bucket"


def test_query_aggregates_1h_collapses_same_topic_across_sensors(
    metadata_store, readings_store
) -> None:
    """1h aggregates collapse same-hour same-topic readings across sensors."""
    plant_id = metadata_store.upsert_plant(name="Test Plant")
    sensor_one_id = metadata_store.register_sensor(
        SensorDescriptor(
            id=-1, plant_id=plant_id, name="temp-a", pin=4, read_interval=120
        )
    )
    sensor_two_id = metadata_store.register_sensor(
        SensorDescriptor(
            id=-1, plant_id=plant_id, name="temp-b", pin=5, read_interval=120
        )
    )

    base_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp()
    values_by_sensor = {
        sensor_one_id: [10.0, 20.0, 30.0],
        sensor_two_id: [40.0, 50.0, 60.0],
    }
    offset = 0
    for sensor_id, values in values_by_sensor.items():
        for value in values:
            readings_store.ingest_reading(
                ProcessedSensorData(
                    plant_id=plant_id,
                    sensor_id=sensor_id,
                    timestamp=base_time + offset,
                    value=value,
                    unit="°C",
                    topic=Topics.TEMPERATURE,
                    correlation_id=f"combined-{sensor_id}-{offset}",
                    flags={ValidationFlag.VALID: True},
                    dq_score=1.0,
                    imputed=False,
                )
            )
            offset += 600

    with readings_store.engine.connect().execution_options(
        isolation_level="AUTOCOMMIT"
    ) as conn:
        conn.execute(
            text("CALL refresh_continuous_aggregate('sensor_readings_1h', NULL, NULL);")
        )
        conn.commit()

    aggregates = readings_store.query_aggregates(
        ReadingsQuery(
            plant_id=plant_id,
            topic=Topics.TEMPERATURE.value,
            since=base_time - 60,
            until=base_time + 3600,
            window="1h",
        )
    )

    assert len(aggregates) == 1
    aggregate = aggregates[0]
    assert aggregate.sample_count == 6
    assert aggregate.mean_value == pytest.approx(35.0)
    assert aggregate.min_value == 10.0
    assert aggregate.max_value == 60.0
    assert aggregate.variance_value == pytest.approx(350.0)
    assert aggregate.stddev_value == pytest.approx(350.0**0.5)
    assert aggregate.skewness_value == pytest.approx(0.0, abs=1e-12)


def test_save_alert_event_requires_registered_definition(
    metadata_store, alert_store
) -> None:
    """Fail fast when saving an event without a pre-registered definition.

    Parameters
    ----------
    metadata_store : MetadataStore
        Store used for relational setup.
    alert_store : AlertsStore
        Store used for alert persistence.

    Returns
    -------
    None
        The assertions raise if alert definition enforcement regresses.
    """
    plant_id = metadata_store.upsert_plant(name="Test Plant")
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
        alert_store.save_alert_event(event)

    with alert_store.engine.connect() as conn:
        assert (
            conn.execute(text("SELECT COUNT(*) FROM alert_history")).scalar_one() == 0
        )


def test_save_and_load_sensor_alert_event(metadata_store, alert_store) -> None:
    """Persist a sensor alert event and reconstruct it from storage.

    Parameters
    ----------
    metadata_store : MetadataStore
        Store used for relational setup.
    alert_store : AlertsStore
        Store used for alert persistence.

    Returns
    -------
    None
        The assertions raise if alert event persistence regresses.
    """
    plant_id = metadata_store.upsert_plant(name="Test Plant")
    sensor_id = metadata_store.register_sensor(
        SensorDescriptor(
            id=-1, plant_id=plant_id, name="DHT22", pin=4, read_interval=120
        )
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
    alert_store.save_alert_definition(definition)

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

    event_id = alert_store.save_alert_event(event)
    assert event_id > 0

    history = alert_store.get_alert_history(AlertHistoryQuery(plant_id=plant_id))
    assert len(history) == 1
    saved_event = history[0]

    assert isinstance(saved_event, SensorAlertEvent)
    assert saved_event.reading.value == 35.0
    assert saved_event.threshold_op == ">"


def test_save_and_load_external_alert_event(metadata_store, alert_store) -> None:
    """Persist an external alert event and reconstruct it from storage.

    Parameters
    ----------
    metadata_store : MetadataStore
        Store used for relational setup.
    alert_store : AlertsStore
        Store used for alert persistence.

    Returns
    -------
    None
        The assertions raise if external alert persistence regresses.
    """
    plant_id = metadata_store.upsert_plant(name="Test Plant")
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
    alert_store.save_alert_definition(definition)

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

    alert_store.save_alert_event(event)
    history = alert_store.get_alert_history(AlertHistoryQuery(plant_id=plant_id))

    assert len(history) == 1
    saved_event = history[0]
    assert isinstance(saved_event, ExternalAlertEvent)
    assert saved_event.metadata["wind_speed"] == "100km/h"


def test_alert_history_closed_window_ignores_limit(metadata_store, alert_store) -> None:
    plant_id = metadata_store.upsert_plant(name="Alert Window Plant")
    definition = AlertDefinition(
        alert_key="weather:window",
        plant_id=plant_id,
        sensor_id=None,
        source="weather_api",
        rule_id=None,
        rule_name="Window Warning",
        kind=AlertType.EXTERNAL,
        persistence_count=0,
        cooldown_seconds=0,
    )
    alert_store.save_alert_definition(definition)

    for timestamp in (100.0, 200.0, 300.0):
        alert_store.save_alert_event(
            ExternalAlertEvent(
                alert_key=definition.alert_key,
                plant_id=plant_id,
                timestamp=timestamp,
                status=AlertStatus.ACTIVE,
                severity=SeverityLevel.WARNING,
                message="Window alert",
                correlation_id=f"alert-window-{timestamp}",
                metadata={},
            )
        )

    history = alert_store.get_alert_history(
        AlertHistoryQuery(plant_id=plant_id, limit=1, since=100.0, until=200.0)
    )

    assert [event.timestamp for event in history] == pytest.approx([200.0, 100.0])


def test_save_external_alert_event_does_not_json_dump_in_storage(
    metadata_store, alert_store, monkeypatch
) -> None:
    """Persist an external alert event without storage-layer JSON shaping."""
    plant_id = metadata_store.upsert_plant(name="Test Plant")
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
    alert_store.save_alert_definition(definition)

    event = ExternalAlertEvent(
        alert_key=definition.alert_key,
        plant_id=plant_id,
        timestamp=time.time(),
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.CRITICAL,
        message="Storm approaching",
        correlation_id="corr-ext-2",
        metadata={"wind_speed": "100km/h", "direction": "NW"},
    )

    from dt.communication.adapters import dump

    dumped_event = dump("db_row", event)
    monkeypatch.setattr("dt.data.database.alerts_storage.dump", lambda *_: dumped_event)
    monkeypatch.setattr(
        "json.dumps",
        lambda *args, **kwargs: pytest.fail(
            "storage should not json.dumps alert metadata"
        ),
    )

    event_id = alert_store.save_alert_event(event)
    assert event_id > 0


def test_sensor_alert_details_reject_duplicate_rows(
    metadata_store, alert_store
) -> None:
    """Enforce one sensor detail row per alert_history event."""
    plant_id = metadata_store.upsert_plant(name="Test Plant")
    sensor_id = metadata_store.register_sensor(
        SensorDescriptor(
            id=-1, plant_id=plant_id, name="DHT22", pin=4, read_interval=120
        )
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
    alert_store.save_alert_definition(definition)

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

    event_id = alert_store.save_alert_event(event)

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
    with alert_store.engine.begin() as conn, pytest.raises(IntegrityError):
        conn.execute(
            text(duplicate_query),
            {"alert_history_id": event_id, "plant_id": plant_id},
        )


def test_external_alert_details_reject_duplicate_rows(
    metadata_store, alert_store
) -> None:
    """Enforce one external detail row per alert_history event."""
    plant_id = metadata_store.upsert_plant(name="Test Plant")
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
    alert_store.save_alert_definition(definition)

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

    event_id = alert_store.save_alert_event(event)

    duplicate_query = """
        INSERT INTO alert_external (alert_history_id, plant_id, metadata)
        SELECT alert_history_id, plant_id, metadata
        FROM alert_external
        WHERE alert_history_id = :alert_history_id AND plant_id = :plant_id
    """
    with alert_store.engine.begin() as conn, pytest.raises(IntegrityError):
        conn.execute(
            text(duplicate_query),
            {"alert_history_id": event_id, "plant_id": plant_id},
        )


def test_get_active_alerts_excludes_cleared(metadata_store, alert_store) -> None:
    """Exclude cleared alerts from the active alerts response.

    Parameters
    ----------
    metadata_store : MetadataStore
        Store used for relational setup.
    alert_store : AlertsStore
        Store used for alert persistence.

    Returns
    -------
    None
        The assertions raise if active alert selection regresses.
    """
    plant_id = metadata_store.upsert_plant(name="Test Plant")
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
    alert_store.save_alert_definition(definition)

    alert_store.save_alert_event(
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
    active = alert_store.get_active_alerts(ActiveAlertsQuery(plant_id=plant_id))
    assert len(active) == 1

    alert_store.save_alert_event(
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
    active = alert_store.get_active_alerts(ActiveAlertsQuery(plant_id=plant_id))
    assert active == []


def test_ingest_camera_snapshot_and_get_latest_returns_newest(
    metadata_store,
    snapshot_store,
) -> None:
    """Persist camera snapshots and return the latest snapshot for the plant/topic."""
    plant_id = metadata_store.upsert_plant(name="Camera Plant")
    sensor_id = metadata_store.register_sensor(
        SensorDescriptor(
            id=-1, plant_id=plant_id, name="Camera", pin=-1, read_interval=60
        )
    )

    older = CameraSnapshot(
        plant_id=plant_id,
        sensor_id=sensor_id,
        timestamp=1_735_689_600.0,
        topic=Topics.CAMERA_IMAGE_TOP,
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
        topic=Topics.CAMERA_IMAGE_TOP,
        correlation_id="camera-newer",
        mime_type="image/jpeg",
        image="AQM=",
        width=640,
        height=480,
    )

    first_id = snapshot_store.ingest_camera_snapshot(older)
    second_id = snapshot_store.ingest_camera_snapshot(newer)

    assert first_id > 0
    assert second_id > first_id

    latest = snapshot_store.get_latest_camera_snapshot(plant_id=plant_id)

    assert latest is not None
    assert latest.correlation_id == "camera-newer"
    assert latest.image == "AQM="
    assert latest.topic is Topics.CAMERA_IMAGE_TOP
    assert latest.width == 640
    assert latest.height == 480


def test_get_latest_camera_snapshot_filters_by_plant_and_topic(
    metadata_store, snapshot_store
) -> None:
    """Filter latest camera snapshot by requested plant and topic."""
    plant_one = metadata_store.upsert_plant(name="Plant One")
    plant_two = metadata_store.upsert_plant(name="Plant Two")
    sensor_one = metadata_store.register_sensor(
        SensorDescriptor(
            id=-1, plant_id=plant_one, name="Camera One", pin=-1, read_interval=60
        )
    )
    sensor_two = metadata_store.register_sensor(
        SensorDescriptor(
            id=-1, plant_id=plant_two, name="Camera Two", pin=-1, read_interval=60
        )
    )

    snapshot_store.ingest_camera_snapshot(
        CameraSnapshot(
            plant_id=plant_one,
            sensor_id=sensor_one,
            timestamp=1_735_689_600.0,
            topic=Topics.CAMERA_IMAGE_TOP,
            correlation_id="camera-plant-1",
            mime_type="image/jpeg",
            image="AQI=",
            width=640,
            height=480,
        )
    )
    snapshot_store.ingest_camera_snapshot(
        CameraSnapshot(
            plant_id=plant_two,
            sensor_id=sensor_two,
            timestamp=1_735_689_700.0,
            topic=Topics.CAMERA_IMAGE_TOP,
            correlation_id="camera-plant-2",
            mime_type="image/jpeg",
            image="AQM=",
            width=640,
            height=480,
        )
    )
    snapshot_store.ingest_camera_snapshot(
        CameraSnapshot(
            plant_id=plant_one,
            sensor_id=sensor_one,
            timestamp=1_735_689_800.0,
            topic=Topics.CAMERA_IMAGE_SIDE,
            correlation_id="camera-plant-1-side",
            mime_type="image/jpeg",
            image="AQQ=",
            width=480,
            height=640,
        )
    )

    latest_plant_one = snapshot_store.get_latest_camera_snapshot(plant_id=plant_one)
    latest_top = snapshot_store.get_latest_camera_snapshot(
        plant_id=plant_one,
        topic=Topics.CAMERA_IMAGE_TOP,
    )
    latest_side = snapshot_store.get_latest_camera_snapshot(
        plant_id=plant_one,
        topic=Topics.CAMERA_IMAGE_SIDE,
    )
    missing_plant = snapshot_store.get_latest_camera_snapshot(plant_id=999_999)

    assert latest_plant_one is not None
    assert latest_plant_one.correlation_id == "camera-plant-1-side"
    assert latest_top is not None
    assert latest_top.correlation_id == "camera-plant-1"
    assert latest_side is not None
    assert latest_side.correlation_id == "camera-plant-1-side"
    assert missing_plant is None


def test_query_camera_snapshots_filters_by_time_interval(
    metadata_store, snapshot_store
) -> None:
    """Return only snapshots within the requested time interval."""
    plant_id = metadata_store.upsert_plant(name="Interval Plant")
    sensor_id = metadata_store.register_sensor(
        SensorDescriptor(
            id=-1, plant_id=plant_id, name="Camera", pin=-1, read_interval=60
        )
    )

    for timestamp, correlation_id in (
        (1_735_689_600.0, "camera-early"),
        (1_735_689_700.0, "camera-middle"),
        (1_735_689_800.0, "camera-late"),
    ):
        snapshot_store.ingest_camera_snapshot(
            CameraSnapshot(
                plant_id=plant_id,
                sensor_id=sensor_id,
                timestamp=timestamp,
                topic=Topics.CAMERA_IMAGE_TOP,
                correlation_id=correlation_id,
                mime_type="image/jpeg",
                image="AQI=",
                width=640,
                height=480,
            )
        )

    snapshots = snapshot_store.query_camera_snapshots(
        CameraSnapshotQuery(
            plant_id=plant_id, since=1_735_689_650.0, until=1_735_689_750.0
        )
    )

    assert [snapshot.correlation_id for snapshot in snapshots] == ["camera-middle"]


def test_ingest_camera_snapshot_persists_file_backed_blob(
    metadata_store, snapshot_store
) -> None:
    """Persist snapshot metadata in the DB and raw bytes on the filesystem."""
    plant_id = metadata_store.upsert_plant(name="File-backed Plant")
    sensor_id = metadata_store.register_sensor(
        SensorDescriptor(
            id=-1, plant_id=plant_id, name="Camera", pin=-1, read_interval=60
        )
    )
    snapshot = CameraSnapshot(
        plant_id=plant_id,
        sensor_id=sensor_id,
        timestamp=1_735_689_800.0,
        topic=Topics.CAMERA_IMAGE_TOP,
        correlation_id="camera-file-backed",
        mime_type="image/jpeg",
        image="aGVsbG8=",
        width=320,
        height=240,
    )

    snapshot_id = snapshot_store.ingest_camera_snapshot(snapshot)

    with snapshot_store._get_connection() as conn:
        row = conn.execute(
            text("""
                SELECT file_ref
                FROM camera_snapshots
                WHERE id = :snapshot_id
                """),
            {"snapshot_id": snapshot_id},
        ).fetchone()

    assert row is not None
    assert row.file_ref

    file_path = snapshot_store.storage_root / row.file_ref
    assert file_path.exists()
    assert file_path.read_bytes() == b64decode(snapshot.image)


def test_ingest_camera_snapshot_rolls_back_when_file_write_fails(
    metadata_store, snapshot_store, monkeypatch
) -> None:
    """Do not commit DB metadata when the snapshot file write fails."""
    plant_id = metadata_store.upsert_plant(name="Rollback Plant")
    sensor_id = metadata_store.register_sensor(
        SensorDescriptor(
            id=-1, plant_id=plant_id, name="Camera", pin=-1, read_interval=60
        )
    )
    snapshot = CameraSnapshot(
        plant_id=plant_id,
        sensor_id=sensor_id,
        timestamp=1_735_689_900.0,
        topic=Topics.CAMERA_IMAGE_TOP,
        correlation_id="camera-write-failure",
        mime_type="image/jpeg",
        image="AQI=",
        width=320,
        height=240,
    )

    def raise_write_failure(*_args, **_kwargs) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(snapshot_store, "_write_snapshot_file", raise_write_failure)

    with pytest.raises(OSError, match="disk full"):
        snapshot_store.ingest_camera_snapshot(snapshot)

    with snapshot_store._get_connection() as conn:
        count = conn.execute(
            text("""
                SELECT COUNT(*)
                FROM camera_snapshots
                WHERE correlation_id = :correlation_id
                """),
            {"correlation_id": snapshot.correlation_id},
        ).scalar_one()

    assert count == 0


def test_get_latest_camera_snapshot_raises_clear_error_when_file_missing(
    metadata_store, snapshot_store
) -> None:
    """Raise a clear runtime error when file-backed snapshot bytes are missing."""
    plant_id = metadata_store.upsert_plant(name="Missing File Plant")
    sensor_id = metadata_store.register_sensor(
        SensorDescriptor(
            id=-1, plant_id=plant_id, name="Camera", pin=-1, read_interval=60
        )
    )
    snapshot = CameraSnapshot(
        plant_id=plant_id,
        sensor_id=sensor_id,
        timestamp=1_735_690_000.0,
        topic=Topics.CAMERA_IMAGE_TOP,
        correlation_id="camera-missing-file",
        mime_type="image/jpeg",
        image="AQM=",
        width=320,
        height=240,
    )
    snapshot_store.ingest_camera_snapshot(snapshot)

    latest_row = None
    with snapshot_store._get_connection() as conn:
        latest_row = conn.execute(
            text("""
                SELECT file_ref
                FROM camera_snapshots
                WHERE correlation_id = :correlation_id
                """),
            {"correlation_id": snapshot.correlation_id},
        ).fetchone()

    assert latest_row is not None
    (snapshot_store.storage_root / latest_row.file_ref).unlink()

    with pytest.raises(RuntimeError, match="Snapshot file not found"):
        snapshot_store.get_latest_camera_snapshot(plant_id=plant_id)


def test_log_action_execution_appends_status_events(
    metadata_store, controller_store
) -> None:
    """Persist one row per action status event for the same execution."""
    plant_id = metadata_store.upsert_plant(name="Action Event Plant")
    actuator_id = metadata_store.register_actuator(plant_id, "Water Pump", 17, 1)

    running = ActionCommand(
        plant_id=plant_id,
        execution_id="exec-append-1",
        action_id="manual:1:1:ON",
        actuator_id=actuator_id,
        event_at=time.time(),
        duration=0.0,
        command="ON",
        reason="append test",
        correlation_id="corr-append-1",
        source="manual",
        status="running",
    )
    completed = ActionCommand(
        plant_id=plant_id,
        execution_id=running.execution_id,
        action_id=running.action_id,
        actuator_id=actuator_id,
        event_at=running.event_at + 1,
        duration=0.0,
        command="ON",
        reason="append test",
        correlation_id="corr-append-1",
        source="manual",
        status="completed",
    )

    controller_store.log_action_execution(running)
    controller_store.log_action_execution(completed)

    history = controller_store.get_action_history(
        ActionHistoryQuery(plant_id=plant_id, limit=10)
    )

    assert [item.status for item in history[:2]] == ["completed", "running"]
    assert {item.execution_id for item in history[:2]} == {"exec-append-1"}
    assert history[0].event_at == pytest.approx(completed.event_at, abs=1e-6)
    assert history[1].event_at == pytest.approx(running.event_at, abs=1e-6)


def test_action_history_closed_window_ignores_limit(
    metadata_store, controller_store
) -> None:
    plant_id = metadata_store.upsert_plant(name="Action Window Plant")
    actuator_id = metadata_store.register_actuator(
        plant_id=plant_id, name="Window Pump", pin=27, relay_channel=1
    )

    for timestamp in (100.0, 200.0, 300.0):
        controller_store.log_action_execution(
            ActionCommand(
                plant_id=plant_id,
                execution_id=f"exec-window-{timestamp}",
                action_id=f"action-window-{timestamp}",
                actuator_id=actuator_id,
                event_at=timestamp,
                duration=0.0,
                command="ON",
                reason="window test",
                correlation_id=f"action-window-{timestamp}",
                source="manual",
                status="completed",
            )
        )

    history = controller_store.get_action_history(
        ActionHistoryQuery(plant_id=plant_id, since=100.0, until=200.0)
    )

    assert [action.event_at for action in history] == pytest.approx([200.0, 100.0])


def test_log_and_get_health_history(metadata_store, db_engine) -> None:
    """Persist health assessments and read them back as typed rows."""
    plant_id = metadata_store.upsert_plant(name="Health History Plant")
    analytics_store = AnalyticsStore(engine=db_engine)
    assessment = HealthAssessment(
        plant_id=plant_id,
        timestamp=1_735_689_600.0,
        correlation_id="health-corr-1",
        state=HealthState.CRITICAL,
        score=0.12,
        summary="Plant is dry and stressed",
        confidence=0.91,
        model_metadata=ModelMetadata(model_name="health-baseline", model_version="1.0"),
    )

    analytics_store.log_health_assessment(assessment)

    history = analytics_store.get_health_history(HealthHistoryQuery(plant_id=plant_id))

    assert history == [assessment]


def test_log_and_get_forecast_history(metadata_store, db_engine) -> None:
    """Persist forecast results and read them back as typed rows."""
    plant_id = metadata_store.upsert_plant(name="Forecast History Plant")
    analytics_store = AnalyticsStore(engine=db_engine)
    forecast = ForecastResult(
        plant_id=plant_id,
        timestamp=1_735_689_700.0,
        correlation_id="forecast-corr-1",
        metric="soil_moisture",
        horizon_seconds=3600,
        predicted_value=24.5,
        unit="%",
        model_metadata=ModelMetadata(
            model_name="moisture-forecaster", model_version="2.0"
        ),
        features_used=["soil_moisture.last", "context.soil_moisture_mean_24h"],
        inference_metadata={"confidence": 0.73},
    )

    analytics_store.log_forecast_result(forecast)

    history = analytics_store.get_forecast_history(
        ForecastHistoryQuery(plant_id=plant_id)
    )

    assert history == [forecast]


def test_recommendation_history_persists_unified_recommendations(
    metadata_store, db_engine
) -> None:
    """Persist unified recommendation events as history rows."""
    plant_id = metadata_store.upsert_plant(name="Lifecycle Plant")
    analytics_store = AnalyticsStore(engine=db_engine)

    first_recommendation = Recommendation(
        plant_id=plant_id,
        timestamp=1_735_689_790.0,
        correlation_id="lifecycle-corr-1",
        confidence=0.61,
        reason="Health is stressed but irrigation guard is not met",
        actions=[RecommendedAction(capability="advisory", command="inspect_plant")],
        model_metadata=ModelMetadata(model_name="policy-engine", model_version="1.0"),
        action_results=[ActionResult(action_index=0, status="advisory_only")],
    )

    second_recommendation = Recommendation(
        plant_id=plant_id,
        timestamp=1_735_689_900.0,
        correlation_id="lifecycle-corr-2",
        confidence=0.94,
        reason="Dry forecast and high confidence",
        actions=[
            RecommendedAction(
                capability="irrigation",
                command="ON",
                duration_seconds=5.0,
            )
        ],
        model_metadata=ModelMetadata(model_name="policy-engine", model_version="1.0"),
        action_results=[ActionResult(action_index=0, status="accepted")],
    )

    analytics_store.log_recommendation(first_recommendation)
    analytics_store.log_recommendation(second_recommendation)

    history = analytics_store.get_recommendation_history(
        RecommendationHistoryQuery(plant_id=plant_id)
    )

    assert history == [second_recommendation, first_recommendation]
