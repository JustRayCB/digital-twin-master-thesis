from datetime import datetime, timezone

import pytest
from pyspark.sql import SparkSession

from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.topics import Topics

from tests.data.preprocess.stream_harness import (
    DEFAULT_TEMPLATE_KEY,
    make_event,
    register_sensors,
    run_pipeline,
    write_config,
)


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
        "validation": {
            "range": {"min": 0.0, "max": 50.0},
            "roc": {"max_per_minute": 5.0},
            "stuck": {"max_flat_seconds": 600},
        },
        "imputation": {
            "strategy": "forward_fill_with_decay",
            "max_gap_seconds": 300,
            "decay_seconds": 120,
            "baseline": None,
        },
        "smoothing": {"strategy": "pass_through"},
    }


def test_end_to_end_calibration_and_normalization(
    spark_session: SparkSession,
    tmp_path,
    configure_preprocess_db_client,
    sensor_registry,
) -> None:
    """Validate calibrated and normalized values emitted by the pipeline."""

    config = {
        "system": {
            "windows": {"small_sec": 60, "medium_sec": 300, "big_sec": 600},
            "weights": {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2},
        },
        "templates": {
            DEFAULT_TEMPLATE_KEY: {
                **_base_sensor_config(),
                "calibration": {"strategy": "affine", "scale": 1.1, "offset": -0.3},
                "normalization": {
                    "strategy": "min_max",
                    "input_min": 15.0,
                    "input_max": 35.0,
                    "output_min": 0.0,
                    "output_max": 1.0,
                    "clip": True,
                },
            }
        },
        "sensors": {
            "greenhouse.temperature": {"template": DEFAULT_TEMPLATE_KEY},
            "sensors.greenhouse.temperature.alpha": {
                "template": DEFAULT_TEMPLATE_KEY,
                "calibration": {"strategy": "affine", "scale": 0.95, "offset": 0.5},
                "normalization": {
                    "strategy": "min_max",
                    "input_min": 10.0,
                    "input_max": 30.0,
                    "output_min": -1.0,
                    "output_max": 1.0,
                    "clip": True,
                },
            },
        },
    }

    config_path = write_config(tmp_path, config)
    sensors = register_sensors(
        sensor_registry,
        ["greenhouse.temperature", "sensors.greenhouse.temperature.alpha"],
    )

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=sensors["greenhouse.temperature"].plant_id,
            sensor_id=sensors["greenhouse.temperature"].id,
            timestamp=base_time.timestamp(),
            value=25.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="default-profile",
        ),
        make_event(
            plant_id=sensors["sensors.greenhouse.temperature.alpha"].plant_id,
            sensor_id=sensors["sensors.greenhouse.temperature.alpha"].id,
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

    default_record = processed_by_sensor[sensors["greenhouse.temperature"].id]
    default_raw = 25.0
    default_calibrated = default_raw * 1.1 - 0.3
    default_normalized = _min_max(default_calibrated, 15.0, 35.0, 0.0, 1.0)
    assert default_record.raw_value == default_raw
    assert default_record.calibrated_value == default_calibrated
    assert default_record.value == default_calibrated
    assert default_record.normalized_value == default_normalized
    assert default_record.calibration_profile_id == DEFAULT_TEMPLATE_KEY
    assert default_record.normalization_profile_id == DEFAULT_TEMPLATE_KEY
    assert default_record.flags[ValidationFlag.VALID] is True
    assert default_record.imputed is False

    override_sensor_key = "sensors.greenhouse.temperature.alpha"
    override_record = processed_by_sensor[sensors[override_sensor_key].id]
    override_raw = 28.0
    override_calibrated = override_raw * 0.95 + 0.5
    override_normalized = _min_max(override_calibrated, 10.0, 30.0, -1.0, 1.0)
    assert override_record.raw_value == override_raw
    assert override_record.calibrated_value == override_calibrated
    assert override_record.value == override_calibrated
    assert override_record.normalized_value == override_normalized
    assert override_record.calibration_profile_id == f"{DEFAULT_TEMPLATE_KEY}:{override_sensor_key}-custom"
    assert override_record.normalization_profile_id == f"{DEFAULT_TEMPLATE_KEY}:{override_sensor_key}-custom"
    assert override_record.flags[ValidationFlag.VALID] is True
    assert override_record.imputed is False
