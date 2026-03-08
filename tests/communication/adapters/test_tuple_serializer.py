"""Tests for new TupleSerializer."""

import pytest

from dt.communication.adapters.serializers.tuple import TupleSerializer
from dt.communication.dataclasses.processed_sensor_data import \
    ProcessedSensorData
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics
from dt.data.preprocess.core.state import FlatlineRecord


def test_tuple_serializer_raw_sensor_roundtrip(raw_sensor_data: RawSensorData):
    serializer = TupleSerializer()
    dumped = serializer.dump(raw_sensor_data)
    loaded = serializer.load(RawSensorData, dumped)
    assert loaded == raw_sensor_data
    assert dumped[5] == Topics.TEMPERATURE.value
    assert type(dumped[5]) is str


def test_tuple_serializer_processed_sensor_roundtrip(
    processed_sensor_data_basic: ProcessedSensorData,
):
    serializer = TupleSerializer()
    dumped = serializer.dump(processed_sensor_data_basic)
    loaded = serializer.load(ProcessedSensorData, dumped)
    assert loaded == processed_sensor_data_basic


def test_tuple_serializer_flatline_roundtrip():
    serializer = TupleSerializer()
    dumped = serializer.dump(FlatlineRecord(value=10.0, timestamp=20.0))
    loaded = serializer.load(FlatlineRecord, dumped)
    assert loaded == FlatlineRecord(value=10.0, timestamp=20.0)
