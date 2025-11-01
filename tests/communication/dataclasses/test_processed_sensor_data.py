import pytest

from dt.communication.dataclasses.processed_sensor_data import (
    ProcessedSensorData,
    ValidationFlag,
)
from dt.communication.topics import Topics


def _sample_processed_payload() -> ProcessedSensorData:
    return ProcessedSensorData(
        plant_id=1,
        sensor_id=42,
        timestamp=1_735_000_000.0,
        value=18.5,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="corr-1",
        flags={ValidationFlag.VALID: True},
        dq_score=0.95,
        imputed=False,
        raw_value=19.0,
        calibrated_value=18.5,
        normalized_value=0.6,
        calibration_profile_id="calibration.greenhouse.temperature.default",
        normalization_profile_id="normalization.greenhouse.temperature.default",
    )


def test_to_dict_preserves_calibration_metadata() -> None:
    processed = _sample_processed_payload()

    as_dict = processed.to_dict()

    assert as_dict["raw_value"] == 19.0
    assert as_dict["calibrated_value"] == 18.5
    assert as_dict["normalized_value"] == 0.6
    assert as_dict["calibration_profile_id"] == "calibration.greenhouse.temperature.default"
    assert as_dict["normalization_profile_id"] == "normalization.greenhouse.temperature.default"


def test_spark_schema_includes_calibration_columns() -> None:
    schema = ProcessedSensorData.get_spark_schema()

    field_names = [field.name for field in schema.fields]
    assert "calibrated_value" in field_names
    assert "calibration_profile_id" in field_names
    assert "normalized_value" in field_names
    assert "normalization_profile_id" in field_names
