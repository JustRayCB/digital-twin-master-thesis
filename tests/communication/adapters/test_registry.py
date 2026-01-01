"""Tests for adapter registry and public API."""

import pytest

from dt.communication.adapters import dump, load
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
    with pytest.raises(KeyError, match="Unknown format"):
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

    with pytest.raises(KeyError, match="Unknown format"):
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
