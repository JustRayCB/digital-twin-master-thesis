"""Tests for TupleAdapter - Python tuple conversions."""

import pytest

from dt.communication.adapters.tuple import TupleAdapter
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics
from dt.data.preprocess.core.state import FlatlineRecord


@pytest.fixture
def adapter():
    """Create a TupleAdapter for tests.

    Returns
    -------
    TupleAdapter
        Adapter instance for tuple conversions.
    """
    return TupleAdapter()


@pytest.fixture
def sample_flatline_record():
    """Create a FlatlineRecord example.

    Returns
    -------
    FlatlineRecord
        Sample flatline record.
    """
    return FlatlineRecord(value=25.3, timestamp=1234567890.5)


def test_dump_returns_tuple(adapter, raw_sensor_data):
    """Verify TupleAdapter.dump returns a tuple.

    Parameters
    ----------
    adapter : TupleAdapter
        Adapter instance under test.
    raw_sensor_data : RawSensorData
        Raw sensor payload to serialize.
    """
    result = adapter.dump(raw_sensor_data)

    assert isinstance(result, tuple)


def test_dump_preserves_field_order(adapter, raw_sensor_data):
    """Verify tuple fields follow dataclass definition order.

    Parameters
    ----------
    adapter : TupleAdapter
        Adapter instance under test.
    raw_sensor_data : RawSensorData
        Raw sensor payload to serialize.
    """
    result = adapter.dump(raw_sensor_data)

    # RawSensorData field order: plant_id, sensor_id, timestamp, value, unit, topic, correlation_id
    assert result[0] == 1  # plant_id
    assert result[1] == 42  # sensor_id
    assert result[2] == 1234567890.5  # timestamp
    assert result[3] == 25.3  # value
    assert result[4] == "Celsius"  # unit


def test_dump_converts_enum_to_value(adapter, raw_sensor_data):
    """Verify Topics enum values serialize as strings.

    Parameters
    ----------
    adapter : TupleAdapter
        Adapter instance under test.
    raw_sensor_data : RawSensorData
        Raw sensor payload to serialize.
    """
    result = adapter.dump(raw_sensor_data)

    # topic is at index 5
    assert isinstance(result[5], str)
    assert result[5] == Topics.TEMPERATURE.value


def test_dump_flatline_record(adapter, sample_flatline_record):
    """Verify TupleAdapter handles simple dataclasses.

    Parameters
    ----------
    adapter : TupleAdapter
        Adapter instance under test.
    sample_flatline_record : FlatlineRecord
        Flatline record to serialize.
    """
    result = adapter.dump(sample_flatline_record)

    assert isinstance(result, tuple)
    assert len(result) == 2
    assert result[0] == 25.3  # value
    assert result[1] == 1234567890.5  # timestamp


def test_load_raw_sensor_data_from_tuple(adapter):
    """Verify TupleAdapter.load reconstructs RawSensorData.

    Parameters
    ----------
    adapter : TupleAdapter
        Adapter instance under test.
    """
    data = (
        1,  # plant_id
        42,  # sensor_id
        1234567890.5,  # timestamp
        25.3,  # value
        "Celsius",  # unit
        Topics.TEMPERATURE.value,  # topic
        "test-123",  # correlation_id
    )

    result = adapter.load(RawSensorData, data)

    assert isinstance(result, RawSensorData)
    assert result.plant_id == 1
    assert result.sensor_id == 42
    assert result.value == 25.3


def test_load_uses_post_init_for_type_coercion(adapter):
    """Verify __post_init__ handles enum coercion.

    Parameters
    ----------
    adapter : TupleAdapter
        Adapter instance under test.
    """
    # topic as string should convert to enum via __post_init__
    data = (1, 42, 1234567890.5, 25.3, "Celsius", Topics.TEMPERATURE.value, "test-123")

    result = adapter.load(RawSensorData, data)

    assert isinstance(result.topic, Topics)
    assert result.topic == Topics.TEMPERATURE


def test_load_flatline_record_from_tuple(adapter):
    """Verify TupleAdapter loads simple dataclasses.

    Parameters
    ----------
    adapter : TupleAdapter
        Adapter instance under test.
    """
    data = (25.3, 1234567890.5)

    result = adapter.load(FlatlineRecord, data)

    assert isinstance(result, FlatlineRecord)
    assert result.value == 25.3
    assert result.timestamp == 1234567890.5


def test_roundtrip_raw_sensor_data(adapter, raw_sensor_data):
    """Verify RawSensorData survives dump/load.

    Parameters
    ----------
    adapter : TupleAdapter
        Adapter instance under test.
    raw_sensor_data : RawSensorData
        Raw sensor payload to serialize.
    """
    dumped = adapter.dump(raw_sensor_data)
    restored = adapter.load(RawSensorData, dumped)

    assert restored == raw_sensor_data


def test_roundtrip_flatline_record(adapter, sample_flatline_record):
    """Verify FlatlineRecord survives dump/load.

    Parameters
    ----------
    adapter : TupleAdapter
        Adapter instance under test.
    sample_flatline_record : FlatlineRecord
        Flatline record to serialize.
    """
    dumped = adapter.dump(sample_flatline_record)
    restored = adapter.load(FlatlineRecord, dumped)

    assert restored == sample_flatline_record
