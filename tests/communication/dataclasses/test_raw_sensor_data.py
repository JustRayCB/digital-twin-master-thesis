import pytest

from dt.communication.topics import Topics
from dt.communication.dataclasses import RawSensorData
from dt.communication.adapters import dump, load


def test_raw_sensor_data_serialization_roundtrip():
    """Ensure RawSensorData enforces typing and round-trips through JSON.

    Returns
    -------
    None
        The assertions raise if serialization deviates from expectations.
    """

    payload = RawSensorData(
        plant_id=3,
        sensor_id=7,
        timestamp=0.5,
        value=42.1,
        unit="lux",
        topic=Topics.LIGHT_INTENSITY,
        correlation_id="abc-123",
    )

    assert payload.plant_id == 3
    assert payload.sensor_id == 7
    assert payload.timestamp == 0.5
    assert payload.value == 42.1
    assert payload.unit == "lux"
    assert payload.topic is Topics.LIGHT_INTENSITY
    assert payload.correlation_id == "abc-123"

    expected_dict = {
        "plant_id": 3,
        "sensor_id": 7,
        "timestamp": 0.5,
        "value": 42.1,
        "unit": "lux",
        "topic": "dt.sensors.light_intensity",
        "correlation_id": "abc-123"
    }
    # Using dump("generic") returns a dict, which is JSON-serializable
    assert dump("generic", payload) == expected_dict

    # Test roundtrip using load("generic") from the dict (which simulates loaded JSON)
    decoded = load("generic", RawSensorData, expected_dict)
    assert decoded == payload


def test_raw_sensor_data_helpers():
    """Verify helper accessors expose dashboard-friendly views of raw data.

    Returns
    -------
    None
        The assertions raise if helper outputs change unexpectedly.
    """

    payload = RawSensorData(
        plant_id=2,
        sensor_id=1,
        timestamp=2,
        value=3.5,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="xyz-789",
    )

    assert payload.shrink_data() == {"value": 3.5, "time": 2}
    assert payload.data_type == "temperature"

    payload.py_to_js_timestamp()
    assert payload.timestamp == 2000


def test_raw_sensor_data_from_json_missing_field():
    """Confirm RawSensorData rejects JSON documents lacking required fields.

    Returns
    -------
    None
        The context manager raises when field validation misbehaves.
    """
    from cattrs.errors import ClassValidationError

    with pytest.raises(ClassValidationError):
        load(
            "generic",
            RawSensorData,
            {
                "plant_id": 2,
                "sensor_id": 1,
                "timestamp": 2.0,
                "value": 3.0,
                "topic": "dt.sensors.temperature",
                "correlation_id": "xyz-789",
            },
        )
