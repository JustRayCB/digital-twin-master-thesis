"""Shared fixtures for communication adapter tests."""

import pytest

from dt.communication.dataclasses.processed_sensor_data import ProcessedSensorData, ValidationFlag
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics


@pytest.fixture
def raw_sensor_data():
    """Create a RawSensorData example.

    Returns
    -------
    RawSensorData
        Sample raw sensor payload.
    """
    return RawSensorData(
        plant_id=1,
        sensor_id=42,
        timestamp=1234567890.5,
        value=25.3,
        unit="Celsius",
        topic=Topics.TEMPERATURE,
        correlation_id="test-123",
    )


@pytest.fixture
def processed_sensor_data_basic():
    """Create a ProcessedSensorData example with minimal flags.

    Returns
    -------
    ProcessedSensorData
        Sample processed sensor payload.
    """
    return ProcessedSensorData(
        plant_id=1,
        sensor_id=42,
        timestamp=1234567890.5,
        value=25.3,
        unit="Celsius",
        topic=Topics.TEMPERATURE,
        correlation_id="test-123",
        flags={
            ValidationFlag.RANGE: True,
            ValidationFlag.RATE_OF_CHANGE: False,
        },
        dq_score=0.95,
        imputed=False,
    )


@pytest.fixture
def processed_sensor_data_full():
    """Create a ProcessedSensorData example with full flags.

    Returns
    -------
    ProcessedSensorData
        Sample processed sensor payload.
    """
    return ProcessedSensorData(
        plant_id=1,
        sensor_id=42,
        timestamp=1234567890.5,
        value=25.3,
        unit="Celsius",
        topic=Topics.TEMPERATURE,
        correlation_id="test-123",
        flags={
            ValidationFlag.RANGE: True,
            ValidationFlag.RATE_OF_CHANGE: True,
            ValidationFlag.STUCK: False,
        },
        dq_score=0.95,
        imputed=False,
    )
