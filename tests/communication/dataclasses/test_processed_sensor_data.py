from collections import namedtuple
from datetime import datetime, timezone

from dt.communication.adapters import dump, load
from dt.communication.dataclasses.processed_sensor_data import ProcessedSensorData, ValidationFlag
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
    """Preserve calibration metadata when dumping to JSON-safe dict.

    Returns
    -------
    None
        Assertions fail if serialized keys or values change.
    """
    processed = _sample_processed_payload()

    as_dict = dump("generic", processed)

    assert as_dict["raw_value"] == 19.0
    assert as_dict["calibrated_value"] == 18.5
    assert as_dict["normalized_value"] == 0.6
    assert as_dict["calibration_profile_id"] == "calibration.greenhouse.temperature.default"
    assert as_dict["normalization_profile_id"] == "normalization.greenhouse.temperature.default"


def test_spark_schema_includes_calibration_columns() -> None:
    """Expose calibration and normalization columns in Spark schema.

    Returns
    -------
    None
        Assertions fail if schema columns regress.
    """
    schema = ProcessedSensorData.get_spark_schema()

    field_names = [field.name for field in schema.fields]
    assert "calibrated_value" in field_names
    assert "calibration_profile_id" in field_names
    assert "normalized_value" in field_names
    assert "normalization_profile_id" in field_names


def test_from_db_row_parses_flags_and_timestamp() -> None:
    """Parse DB row formats into typed flags and numeric timestamps.

    Returns
    -------
    None
        Assertions fail if adapter parsing changes.
    """
    row_type = namedtuple(
        "Row",
        [
            "timestamp",
            "sensor_id",
            "plant_id",
            "topic",
            "value",
            "unit",
            "correlation_id",
            "dq_score",
            "imputed",
            "flags",
            "raw_value",
            "calibrated_value",
            "normalized_value",
            "calibration_profile_id",
            "normalization_profile_id",
        ],
    )
    row = row_type(
        timestamp=datetime.fromtimestamp(1_735_000_000, tz=timezone.utc),
        sensor_id=7,
        plant_id=2,
        topic="temperature",
        value=21.5,
        unit="C",
        correlation_id="corr-flag",
        dq_score=0.9,
        imputed=True,
        flags="range_violation=false|valid_data_point=true",
        raw_value=None,
        calibrated_value=None,
        normalized_value=None,
        calibration_profile_id=None,
        normalization_profile_id=None,
    )

    parsed = load("db_row", ProcessedSensorData, row)

    assert parsed.timestamp == 1_735_000_000.0
    assert parsed.topic == Topics.TEMPERATURE
    assert parsed.flags == {
        ValidationFlag.RANGE: False,
        ValidationFlag.VALID: True,
    }
