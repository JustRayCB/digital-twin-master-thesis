import copy
from datetime import datetime, timedelta, timezone

import pytest
from pyspark.sql import SparkSession

from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.topics import Topics
from tests.data.preprocess.pipeline.pipeline_runner import (
    DEFAULT_TEMPLATE_KEY,
    make_event,
    register_sensors,
    run_pipeline,
)


def _min_max(
    value: float, input_min: float, input_max: float, output_min: float, output_max: float
) -> float:
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


def test_end_to_end_calibration_and_normalization(
    spark_session: SparkSession,
    base_config: dict,
    tmp_path,
    config_writer,
    configure_preprocess_db_client,
    sensor_registry,
) -> None:
    """Validate calibrated and normalized values emitted by the pipeline."""

    config = copy.deepcopy(base_config)
    template = copy.deepcopy(config["templates"][DEFAULT_TEMPLATE_KEY])
    template["calibration"] = {"strategy": "affine", "scale": 1.1, "offset": -0.3}
    template["normalization"] = {
        "strategy": "min_max",
        "input_min": 15.0,
        "input_max": 35.0,
        "output_min": 0.0,
        "output_max": 1.0,
        "clip": True,
    }
    config["templates"][DEFAULT_TEMPLATE_KEY] = template
    config["sensors"]["sensors.greenhouse.temperature.alpha"] = {
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
    }

    config_path = config_writer(config)
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
    assert (
        override_record.calibration_profile_id
        == f"{DEFAULT_TEMPLATE_KEY}:{override_sensor_key}-custom"
    )
    assert (
        override_record.normalization_profile_id
        == f"{DEFAULT_TEMPLATE_KEY}:{override_sensor_key}-custom"
    )
    assert override_record.flags[ValidationFlag.VALID] is True
    assert override_record.imputed is False


def test_min_max_normalization_clips_out_of_bounds_values(
    spark_session: SparkSession,
    base_config: dict,
    tmp_path,
    config_writer,
    configure_preprocess_db_client,
    sensor_registry,
) -> None:
    """Ensure min-max normalization clips values outside the input range."""
    template = copy.deepcopy(base_config["templates"][DEFAULT_TEMPLATE_KEY])
    template["validation"]["range"] = {"min": -100.0, "max": 100.0}
    template["calibration"] = {"strategy": "identity"}
    template["normalization"] = {
        "strategy": "min_max",
        "input_min": 0.0,
        "input_max": 10.0,
        "output_min": 0.0,
        "output_max": 1.0,
        "clip": True,
    }

    config = copy.deepcopy(base_config)
    config["templates"][DEFAULT_TEMPLATE_KEY] = template

    config_path = config_writer(config)
    sensors = register_sensors(sensor_registry, ["greenhouse.temperature"])
    sensor = sensors["greenhouse.temperature"]

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=sensor.plant_id,
            sensor_id=sensor.id,
            timestamp=base_time.timestamp(),
            value=-5.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="clip-low",
        ),
        make_event(
            plant_id=sensor.plant_id,
            sensor_id=sensor.id,
            timestamp=(base_time + timedelta(minutes=10)).timestamp(),
            value=15.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="clip-high",
        ),
    ]

    processed = run_pipeline(spark_session, tmp_path, config_path, events)
    assert len(processed) == 2
    by_corr = {record.correlation_id: record for record in processed}

    low_record = by_corr["clip-low"]
    low_expected = _min_max(-5.0, 0.0, 10.0, 0.0, 1.0)
    assert low_record.raw_value == -5.0
    assert low_record.calibrated_value == -5.0
    assert low_record.value == -5.0
    assert low_record.normalized_value == low_expected

    high_record = by_corr["clip-high"]
    high_expected = _min_max(15.0, 0.0, 10.0, 0.0, 1.0)
    assert high_record.raw_value == 15.0
    assert high_record.calibrated_value == 15.0
    assert high_record.value == 15.0
    assert high_record.normalized_value == high_expected


def test_normalization_uses_imputed_value(
    spark_session: SparkSession,
    base_config: dict,
    tmp_path,
    config_writer,
    configure_preprocess_db_client,
    sensor_registry,
) -> None:
    """Normalization should apply to imputed values when validation fails."""
    template = copy.deepcopy(base_config["templates"][DEFAULT_TEMPLATE_KEY])
    template["calibration"] = {"strategy": "identity"}
    template["normalization"] = {
        "strategy": "min_max",
        "input_min": 10.0,
        "input_max": 30.0,
        "output_min": 0.0,
        "output_max": 1.0,
        "clip": True,
    }

    config = copy.deepcopy(base_config)
    config["templates"][DEFAULT_TEMPLATE_KEY] = template

    config_path = config_writer(config)
    sensors = register_sensors(sensor_registry, ["greenhouse.temperature"])
    sensor = sensors["greenhouse.temperature"]

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=sensor.plant_id,
            sensor_id=sensor.id,
            timestamp=base_time.timestamp(),
            value=20.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="impute-base",
        ),
        make_event(
            plant_id=sensor.plant_id,
            sensor_id=sensor.id,
            timestamp=(base_time + timedelta(seconds=30)).timestamp(),
            value=45.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="impute-violation",
        ),
    ]

    processed = run_pipeline(spark_session, tmp_path, config_path, events)
    assert len(processed) == 2
    record = next(r for r in processed if r.correlation_id == "impute-violation")
    expected_normalized = _min_max(20.0, 10.0, 30.0, 0.0, 1.0)
    assert record.imputed is True
    assert record.value == 20.0
    assert record.raw_value == 45.0
    assert record.calibrated_value == 45.0
    assert record.normalized_value == expected_normalized
    assert record.flags[ValidationFlag.RANGE] is True


def test_piecewise_calibration_strategy_applies_lookup(
    spark_session: SparkSession,
    base_config: dict,
    tmp_path,
    config_writer,
    configure_preprocess_db_client,
    sensor_registry,
) -> None:
    """Piecewise calibration should map inputs to configured segment outputs."""
    template = copy.deepcopy(base_config["templates"][DEFAULT_TEMPLATE_KEY])
    template["validation"]["range"] = {"min": 0.0, "max": 30.0}
    template["calibration"] = {
        "strategy": "piecewise_lookup",
        "segments": [
            {"input_min": 0.0, "input_max": 10.0, "output": 1.0},
            {"input_min": 10.0, "input_max": 20.0, "output": 2.0},
        ],
    }
    template["normalization"] = {"strategy": "identity"}

    config = copy.deepcopy(base_config)
    config["templates"][DEFAULT_TEMPLATE_KEY] = template

    config_path = config_writer(config)
    sensors = register_sensors(sensor_registry, ["greenhouse.temperature"])
    sensor = sensors["greenhouse.temperature"]

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=sensor.plant_id,
            sensor_id=sensor.id,
            timestamp=base_time.timestamp(),
            value=12.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="piecewise",
        )
    ]

    processed = run_pipeline(spark_session, tmp_path, config_path, events)
    assert len(processed) == 1
    record = processed[0]
    assert record.raw_value == 12.0
    assert record.calibrated_value == 2.0
    assert record.value == 2.0
    assert record.normalized_value == 2.0


def test_standalone_sensor_config_profile_ids(
    spark_session: SparkSession,
    base_config: dict[str, object],
    tmp_path,
    config_writer,
    configure_preprocess_db_client,
    sensor_registry,
) -> None:
    """Standalone sensor configs should emit standalone/default profile identifiers."""
    config = copy.deepcopy(base_config)
    config["templates"] = {}
    config["sensors"] = {
        "standalone.temperature": {
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
            "calibration": {"strategy": "identity"},
        }
    }

    config_path = config_writer(config)
    sensors = register_sensors(sensor_registry, ["standalone.temperature"])
    sensor = sensors["standalone.temperature"]

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=sensor.plant_id,
            sensor_id=sensor.id,
            timestamp=base_time.timestamp(),
            value=22.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="standalone-profile",
        )
    ]

    processed = run_pipeline(spark_session, tmp_path, config_path, events)
    assert len(processed) == 1
    record = processed[0]
    assert record.calibration_profile_id == "standalone:standalone.temperature"
    assert record.normalization_profile_id == "default"
