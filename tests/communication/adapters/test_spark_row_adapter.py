"""Tests for SparkRowAdapter - PySpark Row conversions."""

import pytest

# Lazy import to avoid requiring PySpark in all tests
pyspark = pytest.importorskip("pyspark")
from pyspark.sql import Row

from dt.communication.adapters.spark_row import SparkRowAdapter
from dt.communication.dataclasses.processed_sensor_data import (
    ProcessedSensorData,
    ValidationFlag,
)
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics


@pytest.fixture
def adapter():
    """Create a SparkRowAdapter for tests.

    Returns
    -------
    SparkRowAdapter
        Adapter instance for Spark Row conversions.
    """
    return SparkRowAdapter()


def test_dump_processed_data_returns_spark_row(adapter, processed_sensor_data_basic):
    """Verify SparkRowAdapter.dump returns Spark Row.

    Parameters
    ----------
    adapter : SparkRowAdapter
        Adapter instance under test.
    processed_sensor_data_basic : ProcessedSensorData
        Processed payload to serialize.
    """
    result = adapter.dump(processed_sensor_data_basic)

    assert isinstance(result, Row)


def test_dump_converts_topic_to_full_name(adapter, processed_sensor_data_basic):
    """Verify Topics enums serialize as full topic names.

    Parameters
    ----------
    adapter : SparkRowAdapter
        Adapter instance under test.
    processed_sensor_data_basic : ProcessedSensorData
        Processed payload to serialize.
    """
    result = adapter.dump(processed_sensor_data_basic)

    assert result.topic == Topics.TEMPERATURE.value
    assert result.topic == "dt.sensors.temperature"


def test_dump_converts_flags_to_string_keys(adapter, processed_sensor_data_basic):
    """Verify flag keys serialize as strings for Spark.

    Parameters
    ----------
    adapter : SparkRowAdapter
        Adapter instance under test.
    processed_sensor_data_basic : ProcessedSensorData
        Processed payload to serialize.
    """
    result = adapter.dump(processed_sensor_data_basic)

    flags = result.flags
    assert isinstance(flags, dict)
    assert all(isinstance(k, str) for k in flags.keys())
    assert flags[ValidationFlag.RANGE.value] == True
    assert flags[ValidationFlag.RATE_OF_CHANGE.value] == False


def test_load_raw_sensor_data_from_spark_row(adapter):
    """Verify SparkRowAdapter.load reconstructs RawSensorData.

    Parameters
    ----------
    adapter : SparkRowAdapter
        Adapter instance under test.
    """
    row = Row(
        plant_id=1,
        sensor_id=42,
        timestamp=1234567890.5,
        value=25.3,
        unit="Celsius",
        topic=Topics.TEMPERATURE.value,
        correlation_id="test-123",
    )

    result = adapter.load(RawSensorData, row)

    assert isinstance(result, RawSensorData)
    assert result.plant_id == 1
    assert result.value == 25.3


def test_load_converts_topic_string_to_enum(adapter):
    """Verify topic strings load as Topics enums.

    Parameters
    ----------
    adapter : SparkRowAdapter
        Adapter instance under test.
    """
    row = Row(
        plant_id=1,
        sensor_id=42,
        timestamp=1234567890.5,
        value=25.3,
        unit="Celsius",
        topic=Topics.TEMPERATURE.value,
        correlation_id="test-123",
    )

    result = adapter.load(RawSensorData, row)

    assert isinstance(result.topic, Topics)
    assert result.topic == Topics.TEMPERATURE


def test_load_processed_data_converts_flags_to_enum_keys(adapter):
    """Verify flag string keys load as enums.

    Parameters
    ----------
    adapter : SparkRowAdapter
        Adapter instance under test.
    """
    row = Row(
        plant_id=1,
        sensor_id=42,
        timestamp=1234567890.5,
        value=25.3,
        unit="Celsius",
        topic=Topics.TEMPERATURE.value,
        correlation_id="test-123",
        flags={ValidationFlag.RANGE.value: True, ValidationFlag.RATE_OF_CHANGE.value: False},
        dq_score=0.95,
        imputed=False,
    )

    result = adapter.load(ProcessedSensorData, row)

    assert ValidationFlag.RANGE in result.flags
    assert result.flags[ValidationFlag.RANGE] == True
    assert result.flags[ValidationFlag.RATE_OF_CHANGE] == False


def test_roundtrip_raw_sensor_data(adapter, raw_sensor_data):
    """Verify RawSensorData survives dump/load.

    Parameters
    ----------
    adapter : SparkRowAdapter
        Adapter instance under test.
    raw_sensor_data : RawSensorData
        Raw sensor payload to serialize.
    """
    dumped = adapter.dump(raw_sensor_data)
    restored = adapter.load(RawSensorData, dumped)

    assert restored == raw_sensor_data


def test_roundtrip_processed_sensor_data(adapter, processed_sensor_data_basic):
    """Verify ProcessedSensorData survives dump/load.

    Parameters
    ----------
    adapter : SparkRowAdapter
        Adapter instance under test.
    processed_sensor_data_basic : ProcessedSensorData
        Processed payload to serialize.
    """
    dumped = adapter.dump(processed_sensor_data_basic)
    restored = adapter.load(ProcessedSensorData, dumped)

    assert restored == processed_sensor_data_basic
    assert restored.flags == processed_sensor_data_basic.flags
