from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.topics import Topics

_helpers_spec = spec_from_file_location(
    "test_preprocessing_pipeline_helpers",
    Path(__file__).with_name("test_preprocessing_pipeline.py"),
)
_helpers = module_from_spec(_helpers_spec)
assert _helpers_spec.loader is not None
_helpers_spec.loader.exec_module(_helpers)

make_event = _helpers.make_event
run_pipeline = _helpers.run_pipeline
write_config = _helpers.write_config
set_sensor_registry = _helpers.set_sensor_registry


def _min_max(value: float, input_min: float, input_max: float, output_min: float, output_max: float) -> float:
    """Replicate min-max normalization using float arithmetic."""
    ratio = (value - input_min) / (input_max - input_min)
    result = output_min + ratio * (output_max - output_min)
    lower = min(output_min, output_max)
    upper = max(output_min, output_max)
    if result < lower:
        return lower
    if result > upper:
        return upper
    return result


def _base_sensor_config():
    """Return baseline sensor validation settings used in test scenarios."""
    return {
        "units": "C",
        "range": {"min": 0.0, "max": 50.0},
        "roc": {"max_per_minute": 5.0},
        "stuck": {"max_flat_seconds": 600},
    }


def test_end_to_end_calibration_and_normalization(
    spark_session: SparkSession,
    tmp_path,
    mock_db_client,
) -> None:
    """Validate calibrated and normalized values emitted by the pipeline."""

    config = {
        "defaults": {
            "windows": {"small_sec": 60, "medium_sec": 300, "big_sec": 600},
            "scoring": {
                "weights": {
                    "range_ok": 0.5,
                    "roc_ok": 0.3,
                    "stuck_ok": 0.2,
                }
            },
        },
        "sensors": {
            "greenhouse.temperature": _base_sensor_config(),
            "sensors.greenhouse.temperature.alpha": _base_sensor_config(),
        },
        "calibration_profiles": {
            "defaults": {
                "greenhouse.temperature": {
                    "profile_id": "calibration.greenhouse.temperature.default",
                    "strategy": "affine",
                    "parameters": {"scale": 1.1, "offset": -0.3},
                }
            },
            "overrides": {
                "sensors.greenhouse.temperature.alpha": {
                    "sensor_type": "greenhouse.temperature",
                    "profile_id": "calibration.greenhouse.temperature.alpha",
                    "strategy": "affine",
                    "parameters": {"scale": 0.95, "offset": 0.5},
                }
            },
        },
        "normalization_profiles": {
            "defaults": {
                "greenhouse.temperature": {
                    "profile_id": "normalization.greenhouse.temperature.default",
                    "strategy": "min_max",
                    "parameters": {
                        "input_min": 15.0,
                        "input_max": 35.0,
                        "output_min": 0.0,
                        "output_max": 1.0,
                        "clip": True,
                    },
                }
            },
            "overrides": {
                "sensors.greenhouse.temperature.alpha": {
                    "sensor_type": "greenhouse.temperature",
                    "profile_id": "normalization.greenhouse.temperature.alpha",
                    "strategy": "min_max",
                    "parameters": {
                        "input_min": 10.0,
                        "input_max": 30.0,
                        "output_min": -1.0,
                        "output_max": 1.0,
                        "clip": True,
                    },
                }
            },
        },
    }

    config_path = write_config(tmp_path, config)
    set_sensor_registry(
        mock_db_client,
        {
            101: "greenhouse.temperature",
            202: "sensors.greenhouse.temperature.alpha",
        },
    )

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=1,
            sensor_id=101,
            timestamp=base_time.timestamp(),
            value=25.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="default-profile",
        ),
        make_event(
            plant_id=1,
            sensor_id=202,
            timestamp=base_time.timestamp(),
            value=28.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="override-profile",
        ),
    ]

    processed = run_pipeline(spark_session, tmp_path, config_path, events)

    assert len(processed) == 2
    processed_by_sensor = {record.sensor_id: record for record in processed}

    default_record = processed_by_sensor[101]
    default_raw = 25.0
    default_calibrated = default_raw * 1.1 - 0.3
    default_normalized = _min_max(default_calibrated, 15.0, 35.0, 0.0, 1.0)
    assert default_record.raw_value == default_raw
    assert default_record.calibrated_value == default_calibrated
    assert default_record.value == default_calibrated
    assert default_record.normalized_value == default_normalized
    assert default_record.calibration_profile_id == "calibration.greenhouse.temperature.default"
    assert default_record.normalization_profile_id == "normalization.greenhouse.temperature.default"
    assert default_record.flags[ValidationFlag.VALID] is True
    assert default_record.imputed is False

    override_record = processed_by_sensor[202]
    override_raw = 28.0
    override_calibrated = override_raw * 0.95 + 0.5
    override_normalized = _min_max(override_calibrated, 10.0, 30.0, -1.0, 1.0)
    assert override_record.raw_value == override_raw
    assert override_record.calibrated_value == override_calibrated
    assert override_record.value == override_calibrated
    assert override_record.normalized_value == override_normalized
    assert override_record.calibration_profile_id == "calibration.greenhouse.temperature.alpha"
    assert override_record.normalization_profile_id == "normalization.greenhouse.temperature.alpha"
    assert override_record.flags[ValidationFlag.VALID] is True
    assert override_record.imputed is False
