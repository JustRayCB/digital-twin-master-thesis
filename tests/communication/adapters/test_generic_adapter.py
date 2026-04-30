"""Tests for GenericAdapter - Python native type conversions."""

import pytest

from dt.analytics.alerts.rules import SeverityLevel
from dt.communication.adapters.generic import GenericAdapter
from dt.communication.dataclasses.alerts.alert_record import (
    AlertStatus,
    ExternalAlertEvent,
    SensorAlertEvent,
)
from dt.communication.dataclasses.processed_sensor_data import ProcessedSensorData, ValidationFlag
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics


@pytest.fixture
def adapter():
    """Create a GenericAdapter for tests.

    Returns
    -------
    GenericAdapter
        Adapter instance for Python native types.
    """
    return GenericAdapter()


def test_dump_sensor_alert_event(adapter):
    """Verify SensorAlertEvent dumps to dict with all fields.

    Parameters
    ----------
    adapter : GenericAdapter
        Adapter instance under test.
    """
    reading = ProcessedSensorData(
        plant_id=1,
        sensor_id=42,
        timestamp=1234567890.0,
        value=30.5,
        unit="Celsius",
        topic=Topics.TEMPERATURE,
        correlation_id="test-123",
        flags={ValidationFlag.RANGE: True},
        dq_score=1.0,
        imputed=False,
    )

    alert = SensorAlertEvent(
        alert_key="high_temp:temperature",
        plant_id=1,
        timestamp=1234567890.0,
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.WARNING,
        message="Temp too high",
        correlation_id="test-123",
        reading=reading,
        threshold_value=30.0,
        threshold_op=">",
    )

    result = adapter.dump(alert)
    assert result["alert_key"] == "high_temp:temperature"
    assert result["status"] == "active"
    assert result["reading"]["value"] == 30.5


def test_dump_raw_sensor_data_returns_dict(adapter, raw_sensor_data):
    """Verify RawSensorData dumps to dict.

    Parameters
    ----------
    adapter : GenericAdapter
        Adapter instance under test.
    raw_sensor_data : RawSensorData
        Raw sensor payload to serialize.
    """
    result = adapter.dump(raw_sensor_data)
    assert isinstance(result, dict)


def test_dump_raw_sensor_data_contains_all_fields(adapter, raw_sensor_data):
    """Verify RawSensorData dump contains all fields.

    Parameters
    ----------
    adapter : GenericAdapter
        Adapter instance under test.
    raw_sensor_data : RawSensorData
        Raw sensor payload to serialize.
    """
    result = adapter.dump(raw_sensor_data)

    assert result["plant_id"] == 1
    assert result["sensor_id"] == 42
    assert result["timestamp"] == 1234567890.5
    assert result["value"] == 25.3
    assert result["unit"] == "Celsius"
    assert result["correlation_id"] == "test-123"


def test_dump_converts_topic_enum_to_string(adapter, raw_sensor_data):
    """Verify topic enum dumps to string values.

    Parameters
    ----------
    adapter : GenericAdapter
        Adapter instance under test.
    raw_sensor_data : RawSensorData
        Raw sensor payload to serialize.
    """
    result = adapter.dump(raw_sensor_data)

    # Should be string, not enum
    assert isinstance(result["topic"], str)
    assert result["topic"] == Topics.TEMPERATURE.value


def test_dump_processed_data_converts_flags_to_string_keys(adapter, processed_sensor_data_full):
    """Verify flags dump with string keys for JSON.

    Parameters
    ----------
    adapter : GenericAdapter
        Adapter instance under test.
    processed_sensor_data_full : ProcessedSensorData
        Processed payload to serialize.
    """
    result = adapter.dump(processed_sensor_data_full)

    assert isinstance(result["flags"], dict)
    # Keys should be strings
    assert all(isinstance(k, str) for k in result["flags"].keys())
    # Check specific conversions
    assert result["flags"]["range_violation"] == True
    assert result["flags"]["stuck_violation"] == False


def test_dump_external_alert_event(adapter):
    """Verify ExternalAlertEvent dump includes metadata.

    Parameters
    ----------
    adapter : GenericAdapter
        Adapter instance under test.
    """
    alert = ExternalAlertEvent(
        alert_key="ai_anomaly",
        plant_id=1,
        timestamp=1234567890.0,
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.WARNING,
        message="Anomaly detected",
        correlation_id="test-123",
        metadata={"model": "v1.2", "confidence": "0.85"},
    )

    result = adapter.dump(alert)

    assert result["alert_key"] == "ai_anomaly"
    assert result["metadata"]["model"] == "v1.2"
    assert result["severity"] == "warning"


def test_load_raw_sensor_data_from_dict(adapter):
    """Verify RawSensorData loads from dict.

    Parameters
    ----------
    adapter : GenericAdapter
        Adapter instance under test.
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

    result = adapter.load(RawSensorData, data)

    assert isinstance(result, RawSensorData)
    assert result.plant_id == 1
    assert result.sensor_id == 42
    assert result.value == 25.3


def test_load_converts_string_topic_to_enum(adapter):
    """Verify topic strings load as Topics enums.

    Parameters
    ----------
    adapter : GenericAdapter
        Adapter instance under test.
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

    result = adapter.load(RawSensorData, data)

    assert isinstance(result.topic, Topics)
    assert result.topic == Topics.TEMPERATURE


def test_load_processed_data_converts_flags_to_enum_keys(adapter):
    """Verify flag string keys load as enums.

    Parameters
    ----------
    adapter : GenericAdapter
        Adapter instance under test.
    """
    data = {
        "plant_id": 1,
        "sensor_id": 42,
        "timestamp": 1234567890.5,
        "value": 25.3,
        "unit": "Celsius",
        "topic": Topics.TEMPERATURE.value,
        "correlation_id": "test-123",
        "flags": {
            ValidationFlag.RANGE.value: True,
            ValidationFlag.RATE_OF_CHANGE.value: True,
            ValidationFlag.STUCK.value: False,
        },
        "dq_score": 0.95,
        "imputed": False,
    }

    result = adapter.load(ProcessedSensorData, data)

    # Flags should have enum keys
    assert ValidationFlag.RANGE in result.flags
    assert result.flags[ValidationFlag.RANGE] == True
    assert result.flags[ValidationFlag.STUCK] == False


def test_load_sensor_alert_event_from_dict(adapter):
    """Verify SensorAlertEvent loads from dict.

    Parameters
    ----------
    adapter : GenericAdapter
        Adapter instance under test.
    """
    data = {
        "alert_key": "high_temp:temperature",
        "plant_id": 1,
        "timestamp": 1234567890.0,
        "status": "active",
        "severity": "critical",
        "message": "Temp too high",
        "correlation_id": "test-123",
        "acknowledged_by": None,
        "acknowledged_ts": None,
        "cleared_ts": None,
        "threshold_value": 30.5,
        "threshold_op": ">",
        "range_min": None,
        "range_max": None,
        "reading": {
            "plant_id": 1,
            "sensor_id": 42,
            "timestamp": 1234567890.0,
            "value": 30.5,
            "unit": "Celsius",
            "topic": Topics.TEMPERATURE.value,
            "correlation_id": "test-123",
            "flags": {ValidationFlag.RANGE.value: True},
            "dq_score": 1.0,
            "imputed": False,
        },
    }

    result = adapter.load(SensorAlertEvent, data)

    assert isinstance(result, SensorAlertEvent)
    assert result.alert_key == "high_temp:temperature"
    assert result.threshold_value == 30.5
    assert isinstance(result.reading, ProcessedSensorData)
    assert result.reading.value == 30.5


def test_roundtrip_raw_sensor_data(adapter, raw_sensor_data):
    """Verify RawSensorData survives dump/load.

    Parameters
    ----------
    adapter : GenericAdapter
        Adapter instance under test.
    raw_sensor_data : RawSensorData
        Raw sensor payload to serialize.
    """
    dumped = adapter.dump(raw_sensor_data)
    restored = adapter.load(RawSensorData, dumped)

    assert restored == raw_sensor_data


def test_roundtrip_processed_sensor_data(adapter, processed_sensor_data_full):
    """Verify ProcessedSensorData survives dump/load.

    Parameters
    ----------
    adapter : GenericAdapter
        Adapter instance under test.
    processed_sensor_data_full : ProcessedSensorData
        Processed payload to serialize.
    """
    dumped = adapter.dump(processed_sensor_data_full)
    restored = adapter.load(ProcessedSensorData, dumped)

    assert restored == processed_sensor_data_full
    # Extra check on flags
    assert restored.flags == processed_sensor_data_full.flags


def test_roundtrip_sensor_alert_event(adapter):
    """Verify SensorAlertEvent survives dump/load.

    Parameters
    ----------
    adapter : GenericAdapter
        Adapter instance under test.
    """
    reading = ProcessedSensorData(
        plant_id=1,
        sensor_id=42,
        timestamp=1234567890.0,
        value=30.5,
        unit="Celsius",
        topic=Topics.TEMPERATURE,
        correlation_id="test-123",
        flags={ValidationFlag.RANGE: True},
        dq_score=1.0,
        imputed=False,
    )

    alert = SensorAlertEvent(
        alert_key="high_temp:temperature",
        plant_id=1,
        timestamp=1234567890.0,
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.CRITICAL,
        message="Temp too high",
        correlation_id="test-123",
        reading=reading,
        threshold_value=30.0,
        threshold_op=">",
    )

    dumped = adapter.dump(alert)
    restored = adapter.load(SensorAlertEvent, dumped)

    assert restored == alert
    assert isinstance(restored, SensorAlertEvent)
    assert restored.reading == reading
