"""Tests for adapter registry and public API."""

import json
from collections import namedtuple

import pytest

from dt.communication.adapters import dump, load
from dt.communication.dataclasses.aggregated_reading import AggregatedReading
from dt.communication.dataclasses.controller import (
    Action,
    CompiledRule,
    RoutineGraph,
    RoutineUpdate,
    Trigger,
)
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics


def test_dump_with_valid_format(raw_sensor_data):
    """Verify dump routes to the correct adapter.

    Returns
    -------
    None
        Assertions validate behavior.
    """
    result = dump("generic", raw_sensor_data)

    assert isinstance(result, dict)
    assert result["plant_id"] == 1


def test_dump_with_unknown_format_raises_error(raw_sensor_data):
    """Verify dump rejects unknown adapter formats.

    Returns
    -------
    None
        Assertions validate behavior.
    """
    with pytest.raises(KeyError, match="No serializer for"):
        dump("unknown_format", raw_sensor_data)


def test_load_with_valid_format():
    """Verify load routes to the correct adapter.

    Returns
    -------
    None
        Assertions validate behavior.
    """
    data = {
        "plant_id": 1,
        "sensor_id": 42,
        "timestamp": 1234567890.5,
        "value": 25.3,
        "unit": "Celsius",
        "topic": Topics.TEMPERATURE.value,
        "correlation_id": "test-123",
    }

    result = load("generic", RawSensorData, data)

    assert isinstance(result, RawSensorData)
    assert result.plant_id == 1


def test_load_with_unknown_format_raises_error():
    """Verify load rejects unknown adapter formats.

    Returns
    -------
    None
        Assertions validate behavior.
    """
    data = {"plant_id": 1}

    with pytest.raises(KeyError, match="No serializer for"):
        load("unknown_format", RawSensorData, data)


def test_roundtrip_through_registry(raw_sensor_data):
    """Verify dump/load roundtrip via registry.

    Returns
    -------
    None
        Assertions validate behavior.
    """
    dumped = dump("generic", raw_sensor_data)
    restored = load("generic", RawSensorData, dumped)

    assert restored == raw_sensor_data


def test_db_row_uses_default_serializer_when_type_is_not_registered(raw_sensor_data):
    dumped = dump("db_row", raw_sensor_data)
    row = namedtuple("Row", dumped.keys())(*dumped.values())

    restored = load("db_row", RawSensorData, row)

    assert dumped["topic"] == Topics.TEMPERATURE.value
    assert restored == raw_sensor_data


def test_spark_row_uses_default_serializer_when_type_is_not_registered():
    expected = AggregatedReading(
        bucket=1234567800.0,
        sensor_id=42,
        plant_id=1,
        topic=Topics.TEMPERATURE,
        unit="Celsius",
        avg_value=25.0,
        min_value=20.0,
        max_value=30.0,
        sample_count=10,
        avg_dq_score=0.9,
        imputed_count=2,
    )
    dumped = {
        "bucket": expected.bucket,
        "sensor_id": expected.sensor_id,
        "plant_id": expected.plant_id,
        "topic": expected.topic.value,
        "unit": expected.unit,
        "avg_value": expected.avg_value,
        "min_value": expected.min_value,
        "max_value": expected.max_value,
        "sample_count": expected.sample_count,
        "avg_dq_score": expected.avg_dq_score,
        "imputed_count": expected.imputed_count,
    }
    row = namedtuple("Row", dumped.keys())(*dumped.values())

    restored = load("spark_row", AggregatedReading, row)

    assert restored == expected


def test_db_row_uses_routine_serializer_for_routine_update():
    routine = RoutineUpdate(
        plant_id=1,
        name="Routine",
        graph=RoutineGraph(nodes=[], edges=[], name="Routine", plant_id=1),
        compiled_rules=[
            CompiledRule(
                id="rule-1",
                trigger=Trigger(type="sensor", topic=Topics.TEMPERATURE, op=">", value=25.0),
                actions=[Action(actuator_id=1, command="ON", duration=5.0)],
            )
        ],
    )

    dumped = dump("db_row", routine)

    assert isinstance(dumped["graph"], str)
    assert isinstance(dumped["compiled_rules"], str)
    assert json.loads(dumped["graph"])["name"] == "Routine"
    assert json.loads(dumped["compiled_rules"])[0]["id"] == "rule-1"
