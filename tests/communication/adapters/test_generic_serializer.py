"""Tests for GenericSerializer."""

from dt.communication.adapters.serializers.generic.base import \
    GenericSerializer
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics


def test_generic_serializer_dump_returns_dict(raw_sensor_data):
    serializer = GenericSerializer()
    dumped = serializer.dump(raw_sensor_data)
    assert dumped["topic"] == Topics.TEMPERATURE.value
    assert type(dumped["topic"]) is str
    assert dumped["sensor_id"] == 42


def test_generic_serializer_load_builds_target_dataclass():
    serializer = GenericSerializer()
    data = {
        "plant_id": 1,
        "sensor_id": 42,
        "timestamp": 1234567890.5,
        "value": 25.3,
        "unit": "Celsius",
        "topic": Topics.TEMPERATURE.value,
        "correlation_id": "test-123",
    }
    loaded = serializer.load(RawSensorData, data)
    assert isinstance(loaded, RawSensorData)
    assert loaded.topic == Topics.TEMPERATURE
