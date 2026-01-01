"""Tests for Socket.IO payload shaping of processed readings."""

from dt.communication.dataclasses.processed_sensor_data import ProcessedSensorData, ValidationFlag
from dt.communication.topics import Topics
from dt.webapp.consumer import shape_processed_reading_payload


def test_shape_processed_reading_payload_emits_ms_timestamp_and_expected_keys():
    """Ensure processed reading payload matches the browser contract (ms timestamps)."""
    reading = ProcessedSensorData(
        plant_id=1,
        sensor_id=2,
        timestamp=1735689600.0,
        value=42.0,
        unit="%",
        topic=Topics.SOIL_MOISTURE,
        correlation_id="corr-123",
        flags={ValidationFlag.VALID: True, ValidationFlag.RANGE: False},
        dq_score=0.95,
        imputed=False,
        raw_value=41.0,
        calibrated_value=43.0,
        normalized_value=0.72,
        calibration_profile_id="cal-v1",
        normalization_profile_id="norm-v2",
    )

    payload = shape_processed_reading_payload(reading)

    assert payload == {
        "plant_id": 1,
        "sensor_id": 2,
        "time": 1735689600000,
        "unit": "%",
        "value": 42.0,
        "raw_value": 41.0,
        "calibrated_value": 43.0,
        "normalized_value": 0.72,
        "dq_score": 0.95,
        "imputed": False,
        "flags": {"valid_data_point": True, "range_violation": False},
        "correlation_id": "corr-123",
        "calibration_profile_id": "cal-v1",
        "normalization_profile_id": "norm-v2",
    }
