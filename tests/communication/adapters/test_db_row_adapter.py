"""Tests for DbRowAdapter - database row conversions."""

import json
from datetime import datetime
from typing import Iterable

import pytest
from sqlalchemy import JSON, DateTime, create_engine, literal, select
from sqlalchemy.engine import Row

from dt.analytics.alerts.rules import SeverityLevel
from dt.communication.adapters.db_row import DbRowAdapter
from dt.communication.dataclasses.aggregated_reading import AggregatedReading
from dt.communication.dataclasses.alerts.alert_record import (
    AlertDefinition,
    AlertHistoryEvent,
    AlertStatus,
    ExternalAlertEvent,
    SensorAlertEvent,
)
from dt.communication.dataclasses.alerts.alert_type import AlertType
from dt.communication.dataclasses.camera_snapshot import CameraSnapshot
from dt.communication.dataclasses.controller import (
    Action,
    CompiledRule,
    RoutineEdge,
    RoutineGraph,
    RoutineNode,
    RoutineUpdate,
    Trigger,
)
from dt.communication.dataclasses.processed_sensor_data import (
    ProcessedSensorData,
    ValidationFlag,
)
from dt.communication.topics import Topics

_ENGINE = create_engine("sqlite+pysqlite:///:memory:", future=True)


def make_row(
    values: dict[str, object],
    datetime_fields: Iterable[str] | None = None,
    json_fields: Iterable[str] | None = None,
) -> Row:
    """Create a SQLAlchemy Row from literal values. We are using an in-memory SQLite engine.

    Parameters
    ----------
    values : dict[str, object]
        Mapping of column names to literal values.
    datetime_fields : Iterable[str] or None
        Column names that should be treated as DateTime.
    json_fields : Iterable[str] or None
        Column names that should be treated as JSON.

    Returns
    -------
    sqlalchemy.engine.Row
        Row containing the provided values.
    """
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
def adapter():
    """Create a DbRowAdapter for tests.

    Returns
    -------
    DbRowAdapter
        Adapter instance for database conversions.
    """
    return DbRowAdapter()


def test_dump_processed_data_returns_dict(adapter, processed_sensor_data_full):
    """Verify ProcessedSensorData dumps to a dict.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    processed_sensor_data_full : ProcessedSensorData
        Processed payload to serialize.
    """
    result = adapter.dump(processed_sensor_data_full)
    assert isinstance(result, dict)


def test_dump_converts_topic_to_short_name(adapter, processed_sensor_data_full):
    """Verify Topics enums dump to short_name for DB storage.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    processed_sensor_data_full : ProcessedSensorData
        Processed payload to serialize.
    """
    result = adapter.dump(processed_sensor_data_full)

    assert (
        result["topic"] == Topics.TEMPERATURE.short_name
    )  # short_name, not full topic
    assert isinstance(result["topic"], str)


def test_dump_converts_flags_to_pipe_separated_string(
    adapter, processed_sensor_data_full
):
    """Verify flags dump as pipe-separated strings.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    processed_sensor_data_full : ProcessedSensorData
        Processed payload to serialize.
    """
    result = adapter.dump(processed_sensor_data_full)

    flags_text = result["flags"]
    assert isinstance(flags_text, str)
    # Format: "range=true|rate_of_change=true|stuck=false"
    assert f"{ValidationFlag.RANGE.value}=true" in flags_text
    assert f"{ValidationFlag.RATE_OF_CHANGE.value}=true" in flags_text
    assert f"{ValidationFlag.STUCK.value}=false" in flags_text
    assert "|" in flags_text


def test_dump_preserves_other_fields(adapter, processed_sensor_data_full):
    """Verify other fields are preserved in dumps.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    processed_sensor_data_full : ProcessedSensorData
        Processed payload to serialize.
    """
    result = adapter.dump(processed_sensor_data_full)

    assert result["plant_id"] == 1
    assert result["sensor_id"] == 42
    assert result["value"] == 25.3
    assert result["unit"] == "Celsius"
    assert result["dq_score"] == 0.95


def test_dump_routine_update_serializes_compiled_rules(adapter):
    """Serialize compiled rules as JSON for routine persistence.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    """
    graph = RoutineGraph(
        name="Test Routine",
        plant_id=1,
        nodes=[
            RoutineNode(
                id="trigger-1",
                kind="trigger",
                trigger=Trigger(
                    type="sensor", topic=Topics.TEMPERATURE, op=">", value=25.0
                ),
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
            trigger=Trigger(
                type="sensor", topic=Topics.TEMPERATURE, op=">", value=25.0
            ),
            actions=[Action(actuator_id=1, command="ON", duration=5.0)],
        )
    ]

    routine = RoutineUpdate(
        plant_id=1,
        name="Test Routine",
        graph=graph,
        compiled_rules=compiled_rules,
    )

    result = adapter.dump(routine)

    assert isinstance(result["compiled_rules"], str)
    decoded = json.loads(result["compiled_rules"])
    assert decoded == json.loads(
        json.dumps([adapter._generic.dump(rule) for rule in compiled_rules])
    )


def test_load_processed_data_from_named_tuple(adapter):
    """Verify ProcessedSensorData loads from SQLAlchemy rows.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    """
    row = make_row(
        {
            "plant_id": 1,
            "sensor_id": 42,
            "timestamp": datetime.fromtimestamp(1234567890.5),
            "value": 25.3,
            "unit": "Celsius",
            "topic": Topics.TEMPERATURE.short_name,
            "correlation_id": "test-123",
            "flags": (
                f"{ValidationFlag.RANGE.value}=true|{ValidationFlag.RATE_OF_CHANGE.value}="
                f"true|{ValidationFlag.STUCK.value}=false"
            ),
            "dq_score": 0.95,
            "imputed": False,
            "raw_value": 25.3,
            "calibrated_value": None,
            "normalized_value": None,
            "calibration_profile_id": None,
            "normalization_profile_id": None,
        },
        datetime_fields={"timestamp"},
    )

    result = adapter.load(ProcessedSensorData, row)

    assert isinstance(result, ProcessedSensorData)
    assert result.plant_id == 1
    assert result.value == 25.3


def test_load_converts_short_name_to_topic_enum(adapter):
    """Verify short_name strings load as Topics enums.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    """
    row = make_row(
        {
            "plant_id": 1,
            "sensor_id": 42,
            "timestamp": datetime.fromtimestamp(1234567890.5),
            "value": 25.3,
            "unit": "Celsius",
            "topic": Topics.TEMPERATURE.short_name,
            "correlation_id": "test-123",
            "flags": f"{ValidationFlag.RANGE.value}=true",
            "dq_score": 0.95,
            "imputed": False,
            "raw_value": 25.3,
            "calibrated_value": None,
            "normalized_value": None,
            "calibration_profile_id": None,
            "normalization_profile_id": None,
        },
        datetime_fields={"timestamp"},
    )

    result = adapter.load(ProcessedSensorData, row)

    assert isinstance(result.topic, Topics)
    assert result.topic == Topics.TEMPERATURE


def test_load_parses_flags_from_pipe_separated_string(adapter):
    """Verify flag strings parse into enum dictionaries.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    """
    row = make_row(
        {
            "plant_id": 1,
            "sensor_id": 42,
            "timestamp": datetime.fromtimestamp(1234567890.5),
            "value": 25.3,
            "unit": "Celsius",
            "topic": Topics.TEMPERATURE.short_name,
            "correlation_id": "test-123",
            "flags": (
                f"{ValidationFlag.RANGE.value}=true|{ValidationFlag.RATE_OF_CHANGE.value}="
                f"false|{ValidationFlag.STUCK.value}=true"
            ),
            "dq_score": 0.95,
            "imputed": False,
            "raw_value": 25.3,
            "calibrated_value": None,
            "normalized_value": None,
            "calibration_profile_id": None,
            "normalization_profile_id": None,
        },
        datetime_fields={"timestamp"},
    )

    result = adapter.load(ProcessedSensorData, row)

    assert isinstance(result.flags, dict)
    assert ValidationFlag.RANGE in result.flags
    assert result.flags[ValidationFlag.RANGE]
    assert not result.flags[ValidationFlag.RATE_OF_CHANGE]
    assert result.flags[ValidationFlag.STUCK]


def test_load_converts_datetime_to_timestamp(adapter):
    """Verify datetime objects load as Unix timestamps.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    """
    dt_value = datetime.fromtimestamp(1234567890.5)
    row = make_row(
        {
            "plant_id": 1,
            "sensor_id": 42,
            "timestamp": dt_value,
            "value": 25.3,
            "unit": "Celsius",
            "topic": Topics.TEMPERATURE.short_name,
            "correlation_id": "test-123",
            "flags": f"{ValidationFlag.RANGE.value}=true",
            "dq_score": 0.95,
            "imputed": False,
            "raw_value": 25.3,
            "calibrated_value": None,
            "normalized_value": None,
            "calibration_profile_id": None,
            "normalization_profile_id": None,
        },
        datetime_fields={"timestamp"},
    )

    result = adapter.load(ProcessedSensorData, row)

    assert isinstance(result.timestamp, float)
    assert result.timestamp == 1234567890.5


def test_load_aggregated_reading_from_row(adapter):
    """Verify AggregatedReading loads with bucket timestamps.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    """
    row = make_row(
        {
            "plant_id": 1,
            "bucket": datetime.fromtimestamp(1234567800.0),
            "topic": "temperature",
            "unit": "Celsius",
            "mean_value": 25.0,
            "min_value": 24.0,
            "max_value": 26.0,
            "sample_count": 10,
            "avg_dq_score": 0.9,
            "imputed_count": 0,
            "variance_value": 2.5,
            "stddev_value": 1.5811388300841898,
            "skewness_value": 0.25,
        },
        datetime_fields={"bucket"},
    )

    result = adapter.load(AggregatedReading, row)

    assert isinstance(result, AggregatedReading)
    assert result.bucket == 1234567800.0
    assert result.mean_value == 25.0
    assert result.variance_value == 2.5
    assert result.stddev_value == 1.5811388300841898
    assert result.skewness_value == 0.25
    # AggregatedReading stores the topic as a Topics enum.
    assert result.topic == Topics.TEMPERATURE
    assert not hasattr(result, "sensor_id")


def test_roundtrip_processed_sensor_data(adapter, processed_sensor_data_full):
    """Verify ProcessedSensorData survives dump/load.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    processed_sensor_data_full : ProcessedSensorData
        Processed payload to serialize.
    """
    # Dump to dict
    dumped = adapter.dump(processed_sensor_data_full)

    # Simulate database row (convert dict to NamedTuple)
    # Ensure all fields are present for the NamedTuple
    # Extract default values for optional fields if not present in dumped
    # These are usually None or specific defaults set in dataclass definition
    # For simplicity, we'll assume the NamedTuple constructor can handle missing optional fields if they have defaults
    # However, for a NamedTuple used to simulate a DB row, usually all columns are explicit.
    # We'll construct a Row dynamically based on what `dumped` creates.

    # The `dump` method currently returns a dict with all fields, including optional ones as None if not set.
    # We need to ensure the NamedTuple signature matches the keys in 'dumped'.
    row_data = dict(dumped)
    if "timestamp" in row_data:
        row_data["timestamp"] = datetime.fromtimestamp(row_data["timestamp"])

    row = make_row(row_data, datetime_fields={"timestamp"})

    # Load from row
    restored = adapter.load(ProcessedSensorData, row)

    assert restored == processed_sensor_data_full
    assert restored.flags == processed_sensor_data_full.flags
    assert restored.topic == processed_sensor_data_full.topic


def test_dump_alert_definition(adapter):
    """Verify AlertDefinition dumps to flat dict.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    """
    definition = AlertDefinition(
        alert_key="temp_high:sensor_1",
        plant_id=10,
        sensor_id=1,
        source="temperature",
        rule_id="temp_high",
        rule_name="High Temperature Alert",
        kind=AlertType.SENSOR,
        persistence_count=3,
        cooldown_seconds=300,
    )

    result = adapter.dump(definition)

    assert isinstance(result, dict)
    assert result["alert_key"] == "temp_high:sensor_1"
    assert result["plant_id"] == 10
    assert result["kind"] == AlertType.SENSOR.value


def test_load_alert_definition_from_row(adapter):
    """Verify AlertDefinition loads from NamedTuple rows.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    """
    row = make_row(
        {
            "alert_key": "temp_high:sensor_1",
            "plant_id": 10,
            "sensor_id": 1,
            "source": "temperature",
            "rule_id": "temp_high",
            "rule_name": "High Temperature Alert",
            "kind": AlertType.SENSOR,
            "persistence_count": 3,
            "cooldown_seconds": 300,
        }
    )

    result = adapter.load(AlertDefinition, row)

    assert isinstance(result, AlertDefinition)
    assert result.alert_key == "temp_high:sensor_1"
    assert result.plant_id == 10


def test_roundtrip_alert_definition(adapter):
    """Verify AlertDefinition survives dump/load.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    """
    definition = AlertDefinition(
        alert_key="temp_high:sensor_1",
        plant_id=10,
        sensor_id=1,
        source="temperature",
        rule_id="temp_high",
        rule_name="High Temperature Alert",
        kind=AlertType.SENSOR,
        persistence_count=3,
        cooldown_seconds=300,
    )

    dumped = adapter.dump(definition)
    row = make_row(dumped)
    restored = adapter.load(AlertDefinition, row)

    assert restored == definition


def test_dump_alert_history_event(adapter):
    """Verify AlertHistoryEvent dumps with enums as strings.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    """
    event = AlertHistoryEvent(
        alert_key="temp_high:sensor_1",
        plant_id=10,
        timestamp=1234567890.0,
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.CRITICAL,
        message="Temperature exceeded threshold",
        correlation_id="corr-123",
    )

    result = adapter.dump(event)

    assert isinstance(result, dict)
    assert result["alert_key"] == "temp_high:sensor_1"
    assert result["status"] == "active"  # Enum converted to string
    assert result["severity"] == "critical"  # Enum converted to string
    assert result["timestamp"] == 1234567890.0


def test_load_alert_history_event_with_type_coercion(adapter):
    """Verify AlertHistoryEvent loads with enum coercion.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    """
    row = make_row(
        {
            "alert_key": "temp_high:sensor_1",
            "plant_id": 10,
            "timestamp": datetime.fromtimestamp(1234567890.0),
            "status": "active",
            "severity": "critical",
            "message": "Temperature exceeded threshold",
            "correlation_id": "corr-123",
            "acknowledged_by": None,
            "acknowledged_ts": None,
            "cleared_ts": None,
        },
        datetime_fields={"timestamp"},
    )

    result = adapter.load(AlertHistoryEvent, row)

    assert isinstance(result, AlertHistoryEvent)
    assert isinstance(result.status, AlertStatus)
    assert result.status == AlertStatus.ACTIVE  # Converted to enum
    assert isinstance(result.severity, SeverityLevel)
    assert result.severity == SeverityLevel.CRITICAL  # Converted to enum


def test_roundtrip_alert_history_event(adapter):
    """Verify AlertHistoryEvent survives dump/load.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    """
    event = AlertHistoryEvent(
        alert_key="temp_high:sensor_1",
        plant_id=10,
        timestamp=1234567890.0,
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.WARNING,
        message="Temperature exceeded threshold",
        correlation_id="corr-123",
    )

    dumped = adapter.dump(event)
    # Convert timestamp to datetime for simulated DB row
    if "timestamp" in dumped:
        dumped["timestamp"] = datetime.fromtimestamp(dumped["timestamp"])
    if "acknowledged_ts" in dumped and dumped["acknowledged_ts"]:
        dumped["acknowledged_ts"] = datetime.fromtimestamp(dumped["acknowledged_ts"])
    if "cleared_ts" in dumped and dumped["cleared_ts"]:
        dumped["cleared_ts"] = datetime.fromtimestamp(dumped["cleared_ts"])

    row = make_row(
        dumped, datetime_fields={"timestamp", "acknowledged_ts", "cleared_ts"}
    )
    restored = adapter.load(AlertHistoryEvent, row)

    assert restored == event


def test_dump_sensor_alert_event_returns_structured_dict(adapter):
    """Verify SensorAlertEvent dumps with history/sensor keys.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    """
    reading = ProcessedSensorData(
        plant_id=10,
        sensor_id=1,
        timestamp=1234567890.0,
        value=35.0,
        unit="celsius",
        topic=Topics.TEMPERATURE,
        correlation_id="corr-456",
        flags={ValidationFlag.RANGE: True},
        dq_score=0.85,
        imputed=False,
    )

    alert = SensorAlertEvent(
        alert_key="temp_high:sensor_1",
        plant_id=10,
        timestamp=1234567890.0,
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.CRITICAL,
        message="Temperature exceeded threshold",
        correlation_id="corr-456",
        reading=reading,
        threshold_op=">",
        threshold_value=30.0,
    )

    result = adapter.dump(alert)

    # Should return structured dict
    assert isinstance(result, dict)
    assert "history" in result
    assert "sensor" in result

    # History section
    assert result["history"]["alert_key"] == "temp_high:sensor_1"
    assert result["history"]["status"] == "active"
    assert result["history"]["severity"] == "critical"

    # Sensor section
    assert result["sensor"]["sensor_id"] == 1
    assert result["sensor"]["value"] == 35.0
    assert result["sensor"]["threshold_op"] == ">"
    assert result["sensor"]["threshold_value"] == 30.0


def test_dump_sensor_alert_event_applies_db_transformations(adapter):
    """Verify SensorAlertEvent dump applies DB transformations.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    """
    reading = ProcessedSensorData(
        plant_id=10,
        sensor_id=1,
        timestamp=1234567890.0,
        value=35.0,
        unit="celsius",
        topic=Topics.TEMPERATURE,
        correlation_id="corr-456",
        flags={ValidationFlag.RANGE: True, ValidationFlag.STUCK: False},
        dq_score=0.85,
        imputed=False,
    )

    alert = SensorAlertEvent(
        alert_key="temp_high:sensor_1",
        plant_id=10,
        timestamp=1234567890.0,
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.CRITICAL,
        message="Temperature exceeded threshold",
        correlation_id="corr-456",
        reading=reading,
    )

    result = adapter.dump(alert)

    # Topic should be short_name
    assert result["sensor"]["topic"] == Topics.TEMPERATURE.short_name

    # Flags should be pipe-separated string
    assert isinstance(result["sensor"]["flags"], str)
    assert "range_violation=true" in result["sensor"]["flags"]
    assert "stuck_violation=false" in result["sensor"]["flags"]


def test_load_sensor_alert_event_from_tuple_rows(adapter):
    """Verify SensorAlertEvent loads from history/sensor rows.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    """
    history_row = make_row(
        {
            "alert_key": "temp_high:sensor_1",
            "plant_id": 10,
            "timestamp": datetime.fromtimestamp(1234567890.0),
            "status": "active",
            "severity": "critical",
            "message": "Temperature exceeded threshold",
            "correlation_id": "corr-456",
            "acknowledged_by": None,
            "acknowledged_ts": None,
            "cleared_ts": None,
        },
        datetime_fields={"timestamp"},
    )

    sensor_row = make_row(
        {
            "plant_id": 10,
            "sensor_id": 1,
            "timestamp": datetime.fromtimestamp(1234567890.0),
            "value": 35.0,
            "unit": "celsius",
            "topic": Topics.TEMPERATURE.short_name,
            "correlation_id": "corr-456",
            "flags": f"{ValidationFlag.RANGE.value}=true",
            "dq_score": 0.85,
            "imputed": False,
            "raw_value": None,
            "calibrated_value": None,
            "normalized_value": None,
            "calibration_profile_id": None,
            "normalization_profile_id": None,
            "threshold_op": ">",
            "threshold_value": 30.0,
            "range_min": None,
            "range_max": None,
        },
        datetime_fields={"timestamp"},
    )

    result = adapter.load(SensorAlertEvent, (history_row, sensor_row))

    assert isinstance(result, SensorAlertEvent)
    assert result.alert_key == "temp_high:sensor_1"
    assert isinstance(result.reading, ProcessedSensorData)
    assert result.reading.sensor_id == 1
    assert result.reading.value == 35.0
    assert result.threshold_op == ">"
    assert result.threshold_value == 30.0
    assert isinstance(result.status, AlertStatus)
    assert result.status == AlertStatus.ACTIVE
    assert isinstance(result.severity, SeverityLevel)
    assert result.severity == SeverityLevel.CRITICAL


def test_load_sensor_alert_event_type_coercion(adapter):
    """Verify SensorAlertEvent loads with enum coercion.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    """
    history_row = make_row(
        {
            "alert_key": "temp_high:sensor_1",
            "plant_id": 10,
            "timestamp": datetime.fromtimestamp(1234567890.0),
            "status": "active",
            "severity": "warning",
            "message": "Temperature exceeded threshold",
            "correlation_id": "corr-456",
            "acknowledged_by": None,
            "acknowledged_ts": None,
            "cleared_ts": None,
        },
        datetime_fields={"timestamp"},
    )

    sensor_row = make_row(
        {
            "plant_id": 10,
            "sensor_id": 1,
            "timestamp": datetime.fromtimestamp(1234567890.0),
            "value": 35.0,
            "unit": "celsius",
            "topic": Topics.TEMPERATURE.short_name,
            "correlation_id": "corr-456",
            "flags": "",
            "dq_score": 0.85,
            "imputed": False,
            "raw_value": None,
            "calibrated_value": None,
            "normalized_value": None,
            "calibration_profile_id": None,
            "normalization_profile_id": None,
            "threshold_op": None,
            "threshold_value": None,
            "range_min": None,
            "range_max": None,
        },
        datetime_fields={"timestamp"},
    )

    result = adapter.load(SensorAlertEvent, (history_row, sensor_row))

    # Verify type coercion happened
    assert isinstance(result.status, AlertStatus)
    assert result.status == AlertStatus.ACTIVE
    assert isinstance(result.severity, SeverityLevel)
    assert result.severity == SeverityLevel.WARNING


def test_sensor_alert_event_rejects_single_row(adapter):
    """Verify SensorAlertEvent rejects single rows.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    """
    row = make_row({"alert_key": "test", "plant_id": 1})

    with pytest.raises(ValueError, match="SensorAlertEvent requires .* tuple"):
        adapter.load(SensorAlertEvent, row)


def test_dump_external_alert_event_returns_structured_dict(adapter):
    """Verify ExternalAlertEvent dumps with history/external keys.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    """
    alert = ExternalAlertEvent(
        alert_key="ai_anomaly",
        plant_id=10,
        timestamp=1234567890.0,
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.WARNING,
        message="Anomaly detected by AI module",
        correlation_id="corr-999",
        metadata={"model_version": "v1.2", "confidence": "0.85"},
    )

    result = adapter.dump(alert)

    # Should return structured dict
    assert isinstance(result, dict)
    assert "history" in result
    assert "external" in result

    # History section
    assert result["history"]["alert_key"] == "ai_anomaly"
    assert result["history"]["status"] == "active"
    assert result["history"]["severity"] == "warning"

    # External section
    assert result["external"]["plant_id"] == 10
    assert result["external"]["metadata"]["model_version"] == "v1.2"


def test_load_external_alert_event_from_tuple_rows(adapter):
    """Verify ExternalAlertEvent loads from history/external rows.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    """
    history_row = make_row(
        {
            "alert_key": "ai_anomaly",
            "plant_id": 10,
            "timestamp": datetime.fromtimestamp(1234567890.0),
            "status": "active",
            "severity": "warning",
            "message": "Anomaly detected",
            "correlation_id": "corr-999",
            "acknowledged_by": None,
            "acknowledged_ts": None,
            "cleared_ts": None,
        },
        datetime_fields={"timestamp"},
    )

    external_row = make_row(
        {
            "plant_id": 10,
            "metadata": {"model_version": "v1.2", "confidence": "0.85"},
        },
        json_fields={"metadata"},
    )

    result = adapter.load(ExternalAlertEvent, (history_row, external_row))

    assert isinstance(result, ExternalAlertEvent)
    assert result.alert_key == "ai_anomaly"
    assert result.metadata["model_version"] == "v1.2"


def test_load_external_alert_event_type_coercion(adapter):
    """Verify ExternalAlertEvent loads with enum coercion.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    """
    history_row = make_row(
        {
            "alert_key": "ai_anomaly",
            "plant_id": 10,
            "timestamp": datetime.fromtimestamp(1234567890.0),
            "status": "acknowledged",
            "severity": "info",
            "message": "Anomaly detected",
            "correlation_id": "corr-999",
            "acknowledged_by": "user123",
            "acknowledged_ts": None,
            "cleared_ts": None,
        },
        datetime_fields={"timestamp"},
    )

    external_row = make_row({"plant_id": 10, "metadata": {}}, json_fields={"metadata"})

    result = adapter.load(ExternalAlertEvent, (history_row, external_row))

    # Verify type coercion happened
    assert isinstance(result.status, AlertStatus)
    assert result.status == AlertStatus.ACKNOWLEDGED
    assert isinstance(result.severity, SeverityLevel)
    assert result.severity == SeverityLevel.INFO


def test_external_alert_event_rejects_single_row(adapter):
    """Verify ExternalAlertEvent rejects single rows.

    Parameters
    ----------
    adapter : DbRowAdapter
        Adapter instance under test.
    """
    row = make_row({"alert_key": "test", "plant_id": 1})

    with pytest.raises(ValueError, match="ExternalAlertEvent requires .* tuple"):
        adapter.load(ExternalAlertEvent, row)


def test_dump_camera_snapshot_for_db_row(adapter):
    """Verify CameraSnapshot dumps to DB-ready fields."""
    snapshot = CameraSnapshot(
        plant_id=1,
        sensor_id=9,
        timestamp=1735689600.0,
        topic=Topics.CAMERA_IMAGE_TOP,
        correlation_id="cam-corr-1",
        mime_type="image/jpeg",
        image="AQI=",
        width=640,
        height=480,
    )

    dumped = adapter.dump(snapshot)

    assert dumped["topic"] == Topics.CAMERA_IMAGE_TOP.short_name
    assert dumped["image"] == "AQI="
    assert dumped["timestamp"] == 1735689600.0


def test_load_camera_snapshot_from_db_row(adapter):
    """Verify CameraSnapshot loads from DB row with decoded timestamp/topic."""
    row = make_row(
        {
            "plant_id": 1,
            "sensor_id": 9,
            "timestamp": datetime.fromtimestamp(1735689600.0),
            "topic": Topics.CAMERA_IMAGE_TOP.short_name,
            "correlation_id": "cam-corr-2",
            "mime_type": "image/jpeg",
            "image": b"\x01\x02",
            "width": 640,
            "height": 480,
        },
        datetime_fields={"timestamp"},
    )

    loaded = adapter.load(CameraSnapshot, row)

    assert loaded == CameraSnapshot(
        plant_id=1,
        sensor_id=9,
        timestamp=1735689600.0,
        topic=Topics.CAMERA_IMAGE_TOP,
        correlation_id="cam-corr-2",
        mime_type="image/jpeg",
        image="AQI=",
        width=640,
        height=480,
    )
