"""Shared fixtures for communication tests."""

from __future__ import annotations

import pytest

from dt.communication.dataclasses import ProcessedSensorData, SensorDescriptor
from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics


def build_raw_sensor_data(**overrides: object) -> RawSensorData:
    """Build a RawSensorData example with optional overrides."""
    payload = {
        "plant_id": 1,
        "sensor_id": 42,
        "timestamp": 1234567890.5,
        "value": 25.3,
        "unit": "Celsius",
        "topic": Topics.TEMPERATURE,
        "correlation_id": "test-123",
    }
    payload.update(overrides)
    return RawSensorData(**payload)


def build_processed_sensor_data(
    flags: dict[ValidationFlag, bool] | None = None,
    **overrides: object,
) -> ProcessedSensorData:
    """Build a ProcessedSensorData example with optional flags and overrides."""
    payload = {
        "plant_id": 1,
        "sensor_id": 42,
        "timestamp": 1234567890.5,
        "value": 25.3,
        "unit": "Celsius",
        "topic": Topics.TEMPERATURE,
        "correlation_id": "test-123",
        "flags": flags or {ValidationFlag.RANGE: True},
        "dq_score": 0.95,
        "imputed": False,
    }
    payload.update(overrides)
    return ProcessedSensorData(**payload)


@pytest.fixture
def raw_sensor_data() -> RawSensorData:
    """Create a RawSensorData example."""
    return build_raw_sensor_data()


@pytest.fixture
def processed_sensor_data_basic() -> ProcessedSensorData:
    """Create a ProcessedSensorData example with minimal flags."""
    return build_processed_sensor_data(
        flags={
            ValidationFlag.RANGE: True,
            ValidationFlag.RATE_OF_CHANGE: False,
        },
    )


@pytest.fixture
def processed_sensor_data_full() -> ProcessedSensorData:
    """Create a ProcessedSensorData example with full flags."""
    return build_processed_sensor_data(
        flags={
            ValidationFlag.RANGE: True,
            ValidationFlag.RATE_OF_CHANGE: True,
            ValidationFlag.STUCK: False,
        },
    )


@pytest.fixture
def plant_id(metadata_store) -> int:
    """Create a plant used by client integration tests."""
    return metadata_store.upsert_plant(
        name="Communication Test Plant", notes="db_client integration tests"
    )


@pytest.fixture
def sensor(metadata_store, plant_id: int) -> SensorDescriptor:
    """Register a sensor for client integration tests."""
    sensor = SensorDescriptor(
        id=0,
        plant_id=plant_id,
        name="dht22.temperature",
        pin=17,
        read_interval=5,
    )
    sensor.id = metadata_store.register_sensor(sensor)
    return sensor


@pytest.fixture
def reading(sensor: SensorDescriptor) -> ProcessedSensorData:
    """Build a processed reading aligned with the registered sensor."""
    return ProcessedSensorData(
        plant_id=sensor.plant_id,
        sensor_id=sensor.id,
        timestamp=1_735_000_000.0,
        value=21.5,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="corr-1",
        flags={},
        dq_score=0.9,
        imputed=False,
    )
