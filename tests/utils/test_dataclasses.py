import pytest

from dt.communication import Topics
from dt.utils.dataclasses import DBTimestampQuery, SensorData, SensorDataClass


def test_sensor_data_serialization_roundtrip():

    payload = SensorData(
        sensor_id=7,
        timestamp=0.5,
        value=42.1,
        unit="lux",
        topic=Topics.LIGHT_INTENSITY,
    )

    assert payload.sensor_id == 7
    assert payload.timestamp == 0.5
    assert payload.value == 42.1
    assert payload.unit == "lux"
    assert payload.topic is Topics.LIGHT_INTENSITY

    expected_json = (
        '{"sensor_id":7,"timestamp":0.5,"value":42.1,"unit":"lux",'
        '"topic":"dt.sensors.light_intensity"}'
    )
    assert payload.to_json() == expected_json

    decoded = SensorData.from_json(expected_json)
    assert decoded == payload


def test_sensor_data_helpers():

    payload = SensorData(
        sensor_id=1,
        timestamp=2,
        value=3.5,
        unit="C",
        topic=Topics.TEMPERATURE,
    )

    assert payload.shrink_data() == {"value": 3.5, "time": 2}
    assert payload.data_type == "temperature"

    payload.py_to_js_timestamp()
    assert payload.timestamp == 2000


def test_sensor_data_from_json_missing_field():

    with pytest.raises(ValueError, match="Missing field: unit"):
        SensorData.from_json(
            {
                "sensor_id": 1,
                "timestamp": 2.0,
                "value": 3.0,
                "topic": "dt.sensors.temperature",
            }
        )


def test_sensor_metadata():

    metadata = SensorDataClass(sensor_id=1, name="123", pin=11, read_interval=15)

    assert metadata.sensor_id == 1
    assert metadata.name == "123"
    assert metadata.pin == 11
    assert metadata.read_interval == 15

    metadata.change_id(9)
    assert metadata.sensor_id == 9


def test_db_timestamp_query():

    query = DBTimestampQuery(data_type="42", from_timestamp=2000, to_timestamp=5000)

    assert query.data_type == "42"
    assert query.from_timestamp == 2000
    assert query.to_timestamp == 5000

    query.js_to_py_timestamp()
    assert query.from_timestamp == 2
    assert query.to_timestamp == 5

    encoded = {
        "data_type": "soil_moisture",
        "from_timestamp": 1000,
        "to_timestamp": 2000,
    }
    round_trip = DBTimestampQuery.from_json(encoded)
    assert round_trip.data_type == "soil_moisture"
    assert round_trip.from_timestamp == 1000
    assert round_trip.to_timestamp == 2000
