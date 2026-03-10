"""Tests for new DB serializer hierarchy (tasks 4-6)."""

import json
from datetime import datetime
from typing import Iterable

import pytest
from sqlalchemy import JSON, DateTime, create_engine, literal, select
from sqlalchemy.engine import Row

from dt.alerts.rules import SeverityLevel
from dt.communication.adapters.serializers.db.alert import (
    AlertHistoryEventDbSerializer, ExternalAlertEventDbSerializer,
    SensorAlertEventDbSerializer)
from dt.communication.adapters.serializers.db.controller import (
    ActionCommandDbSerializer, ControlModeDbSerializer, RoutineDbSerializer)
from dt.communication.adapters.serializers.db.sensor import (
    AggregatedReadingDbSerializer, CameraSnapshotDbSerializer,
    ProcessedSensorDataDbSerializer)
from dt.communication.dataclasses.aggregated_reading import AggregatedReading
from dt.communication.dataclasses.alerts.alert_record import (
    AlertHistoryEvent, AlertStatus, ExternalAlertEvent, SensorAlertEvent)
from dt.communication.dataclasses.camera_snapshot import CameraSnapshot
from dt.communication.dataclasses.controller import (Action, ActionCommand,
                                                     CompiledRule, ControlMode,
                                                     Routine, RoutineEdge,
                                                     RoutineGraph, RoutineNode,
                                                     Trigger)
from dt.communication.dataclasses.processed_sensor_data import (
    ProcessedSensorData, ValidationFlag)
from dt.communication.topics import Topics

_ENGINE = create_engine("sqlite+pysqlite:///:memory:", future=True)


def make_row(
    values: dict[str, object],
    datetime_fields: Iterable[str] | None = None,
    json_fields: Iterable[str] | None = None,
) -> Row:
    datetime_fields = set(datetime_fields or [])
    json_fields = set(json_fields or [])
    columns = []
    for key, value in values.items():
        if key in datetime_fields:
            columns.append(literal(value, type_=DateTime()).label(key))
        elif key in json_fields:
            columns.append(literal(value, type_=JSON()).label(key))
        else:
            columns.append(literal(value).label(key))
    stmt = select(*columns)
    with _ENGINE.connect() as conn:
        return conn.execute(stmt).first()


@pytest.fixture
def sensor_serializer() -> ProcessedSensorDataDbSerializer:
    return ProcessedSensorDataDbSerializer()


def test_processed_sensor_serializer_dump_db_fields(
    sensor_serializer: ProcessedSensorDataDbSerializer,
    processed_sensor_data_full: ProcessedSensorData,
) -> None:
    dumped = sensor_serializer.dump(processed_sensor_data_full)
    assert dumped["topic"] == Topics.TEMPERATURE.short_name
    assert f"{ValidationFlag.RANGE.value}=true" in dumped["flags"]


def test_processed_sensor_serializer_load_db_fields(
    sensor_serializer: ProcessedSensorDataDbSerializer,
) -> None:
    row = make_row(
        {
            "plant_id": 1,
            "sensor_id": 42,
            "timestamp": datetime.fromtimestamp(1234567890.5),
            "value": 25.3,
            "unit": "Celsius",
            "topic": Topics.TEMPERATURE.short_name,
            "correlation_id": "test-123",
            "flags": f"{ValidationFlag.RANGE.value}=true|{ValidationFlag.STUCK.value}=false",
            "dq_score": 0.95,
            "imputed": False,
            "raw_value": None,
            "calibrated_value": None,
            "normalized_value": None,
            "calibration_profile_id": None,
            "normalization_profile_id": None,
        },
        datetime_fields={"timestamp"},
    )
    loaded = sensor_serializer.load(ProcessedSensorData, row)
    assert loaded.timestamp == 1234567890.5
    assert loaded.topic == Topics.TEMPERATURE
    assert loaded.flags[ValidationFlag.RANGE] is True


def test_aggregated_reading_serializer_loads_topic_and_bucket() -> None:
    serializer = AggregatedReadingDbSerializer()
    row = make_row(
        {
            "bucket": datetime.fromtimestamp(1234567800.0),
            "sensor_id": 42,
            "plant_id": 1,
            "topic": Topics.TEMPERATURE.short_name,
            "unit": "Celsius",
            "mean_value": 25.0,
            "min_value": 20.0,
            "max_value": 30.0,
            "sample_count": 10,
            "avg_dq_score": 0.9,
            "imputed_count": 2,
            "variance_value": 4.0,
            "stddev_value": 2.0,
            "skewness_value": 0.0,
        },
        datetime_fields={"bucket"},
    )
    loaded = serializer.load(AggregatedReading, row)
    assert isinstance(loaded, AggregatedReading)
    assert loaded.bucket == 1234567800.0
    assert loaded.topic == Topics.TEMPERATURE
    assert loaded.variance_value == 4.0
    assert loaded.stddev_value == 2.0
    assert loaded.skewness_value == 0.0


def test_camera_snapshot_serializer_loads_binary_image() -> None:
    serializer = CameraSnapshotDbSerializer()
    row = make_row(
        {
            "plant_id": 1,
            "sensor_id": 7,
            "timestamp": datetime.fromtimestamp(1234.5),
            "topic": Topics.CAMERA_IMAGE.short_name,
            "correlation_id": "cid",
            "mime_type": "image/jpeg",
            "image": b"\x00\x01\xff",
            "width": 800,
            "height": 600,
        },
        datetime_fields={"timestamp"},
    )
    loaded = serializer.load(CameraSnapshot, row)
    assert isinstance(loaded, CameraSnapshot)
    assert loaded.timestamp == 1234.5
    assert loaded.topic == Topics.CAMERA_IMAGE
    assert loaded.image == "AAH/"


def test_alert_history_serializer_loads_timestamps_and_enums() -> None:
    serializer = AlertHistoryEventDbSerializer()
    row = make_row(
        {
            "alert_key": "high_temp:temperature",
            "plant_id": 1,
            "timestamp": datetime.fromtimestamp(1000.0),
            "status": "active",
            "severity": "warning",
            "message": "too hot",
            "correlation_id": "cid",
            "acknowledged_by": "ray",
            "acknowledged_ts": datetime.fromtimestamp(1001.0),
            "cleared_ts": datetime.fromtimestamp(1002.0),
        },
        datetime_fields={"timestamp", "acknowledged_ts", "cleared_ts"},
    )
    loaded = serializer.load(AlertHistoryEvent, row)
    assert isinstance(loaded, AlertHistoryEvent)
    assert loaded.status == AlertStatus.ACTIVE
    assert loaded.severity == SeverityLevel.WARNING
    assert loaded.timestamp == 1000.0


def test_sensor_alert_serializer_dump_and_load(
    processed_sensor_data_full: ProcessedSensorData,
) -> None:
    serializer = SensorAlertEventDbSerializer()
    alert = SensorAlertEvent(
        alert_key="high_temp:temperature",
        plant_id=1,
        timestamp=1234567890.0,
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.CRITICAL,
        message="too hot",
        correlation_id="cid",
        reading=processed_sensor_data_full,
        threshold_op=">",
        threshold_value=30.0,
        range_min=None,
        range_max=None,
    )
    dumped = serializer.dump(alert)
    assert set(dumped.keys()) == {"history", "sensor"}
    assert dumped["sensor"]["topic"] == Topics.TEMPERATURE.short_name
    assert f"{ValidationFlag.RANGE.value}=true" in dumped["sensor"]["flags"]

    history_row = make_row(
        dumped["history"]
        | {
            "id": 10,
            "timestamp": datetime.fromtimestamp(dumped["history"]["timestamp"]),
        },
        datetime_fields={"timestamp", "acknowledged_ts", "cleared_ts"},
    )
    sensor_row = make_row(
        dumped["sensor"]
        | {
            "alert_history_id": 10,
            "timestamp": datetime.fromtimestamp(dumped["sensor"]["timestamp"]),
        },
        datetime_fields={"timestamp"},
    )
    loaded = serializer.load(SensorAlertEvent, (history_row, sensor_row))
    assert isinstance(loaded, SensorAlertEvent)
    assert loaded.reading.topic == Topics.TEMPERATURE
    assert loaded.threshold_value == 30.0


def test_sensor_alert_serializer_requires_tuple() -> None:
    serializer = SensorAlertEventDbSerializer()
    row = make_row({"alert_key": "x"})
    with pytest.raises(ValueError, match="requires"):
        serializer.load(SensorAlertEvent, row)


def test_external_alert_serializer_dump_and_load() -> None:
    serializer = ExternalAlertEventDbSerializer()
    alert = ExternalAlertEvent(
        alert_key="ai_anomaly",
        plant_id=1,
        timestamp=1234567890.0,
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.WARNING,
        message="Anomaly",
        correlation_id="cid",
        metadata={"model": "v1"},
    )
    dumped = serializer.dump(alert)
    assert set(dumped.keys()) == {"history", "external"}

    history_row = make_row(
        dumped["history"]
        | {
            "id": 10,
            "timestamp": datetime.fromtimestamp(dumped["history"]["timestamp"]),
        },
        datetime_fields={"timestamp", "acknowledged_ts", "cleared_ts"},
    )
    external_row = make_row(dumped["external"] | {"alert_history_id": 10}, json_fields={"metadata"})
    loaded = serializer.load(ExternalAlertEvent, (history_row, external_row))
    assert isinstance(loaded, ExternalAlertEvent)
    assert loaded.metadata == {"model": "v1"}


def test_external_alert_serializer_requires_tuple() -> None:
    serializer = ExternalAlertEventDbSerializer()
    row = make_row({"alert_key": "x"})
    with pytest.raises(ValueError, match="requires"):
        serializer.load(ExternalAlertEvent, row)


def test_routine_serializer_dump_load_and_json_handling() -> None:
    serializer = RoutineDbSerializer()
    graph = RoutineGraph(
        name="Routine",
        plant_id=1,
        nodes=[
            RoutineNode(
                id="trigger-1",
                kind="trigger",
                trigger=Trigger(type="sensor", topic=Topics.TEMPERATURE, op=">", value=25.0),
            ),
            RoutineNode(
                id="action-1",
                kind="action",
                action=Action(actuator_id=1, command="ON", duration=5.0),
            ),
        ],
        edges=[RoutineEdge(source="trigger-1", target="action-1")],
    )
    compiled_rules = [
        CompiledRule(
            id="trigger-1",
            trigger=Trigger(type="sensor", topic=Topics.TEMPERATURE, op=">", value=25.0),
            actions=[Action(actuator_id=1, command="ON", duration=5.0)],
        )
    ]
    routine = Routine(
        id=3,
        plant_id=1,
        name="Routine",
        enabled=True,
        graph=graph,
        compiled_rules=compiled_rules,
    )

    dumped = serializer.dump(routine)
    assert isinstance(dumped["graph"], str)
    assert isinstance(dumped["compiled_rules"], str)

    row = make_row(
        {
            "id": 3,
            "plant_id": 1,
            "name": "Routine",
            "enabled": True,
            "graph": json.loads(dumped["graph"]),
            "compiled_rules": dumped["compiled_rules"],
            "created_at": datetime.fromtimestamp(1000.0),
            "updated_at": datetime.fromtimestamp(1001.0),
        },
        datetime_fields={"created_at", "updated_at"},
        json_fields={"graph"},
    )
    loaded = serializer.load(Routine, row)
    assert isinstance(loaded, Routine)
    assert loaded.created_at == datetime.fromtimestamp(1000.0).isoformat()
    assert loaded.updated_at == datetime.fromtimestamp(1001.0).isoformat()


def test_control_mode_serializer_dump_parses_updated_at() -> None:
    serializer = ControlModeDbSerializer()
    mode = ControlMode(
        plant_id=1, ai_autopilot_enabled=True, owner="ai", updated_at="2025-01-01T12:00:00"
    )
    dumped = serializer.dump(mode)
    assert isinstance(dumped["updated_at"], datetime)


def test_action_command_serializer_dump_and_load() -> None:
    serializer = ActionCommandDbSerializer()
    command = ActionCommand(
        plant_id=1,
        execution_id="exec-1",
        action_id="a1",
        actuator_id=2,
        event_at=1000.5,
        duration=30.0,
        command="ON",
        reason="rule",
        correlation_id="cid",
        source="manual",
    )
    dumped = serializer.dump(command)
    assert dumped["execution_id"] == "exec-1"
    assert dumped["event_at"] == 1000.5

    row = make_row(
        {
            "plant_id": 1,
            "execution_id": "exec-1",
            "action_id": "a1",
            "actuator_id": 2,
            "event_at": datetime.fromtimestamp(1000.5),
            "duration": 30.0,
            "command": "ON",
            "reason": "rule",
            "correlation_id": "cid",
            "source": "manual",
            "routine_id": None,
            "status": "completed",
            "error_message": None,
        },
        datetime_fields={"event_at"},
    )
    loaded = serializer.load(ActionCommand, row)
    assert loaded.execution_id == "exec-1"
    assert loaded.event_at == 1000.5
