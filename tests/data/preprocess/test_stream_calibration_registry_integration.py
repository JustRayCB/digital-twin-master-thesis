import copy
from datetime import datetime, timezone
from typing import Any

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


def test_calibration_adjusts_processed_value(
    spark_session: SparkSession,
    base_config: dict[str, Any],
    tmp_path,
    configure_preprocess_db_client,
    sensor_registry,
) -> None:
    """Calibration shifts processed output while preserving raw_value."""
    sensors = register_sensors(sensor_registry, ["greenhouse.temperature"])
    sensor = sensors["greenhouse.temperature"]

    config = copy.deepcopy(base_config)
    config["sensors"]["greenhouse.temperature"]["calibration"] = {
        "strategy": "affine",
        "scale": 1.0,
        "offset": -1.5,
    }
    config_path = write_config(tmp_path, config)

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=sensor.plant_id,
            sensor_id=sensor.id,
            timestamp=base_time.timestamp(),
            value=22.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="calib-1",
        )
    ]

    processed = run_pipeline(spark_session, tmp_path, config_path, events)
    assert len(processed) == 1
    result = processed[0]
    assert result.imputed is False
    assert result.value == 20.5
    assert result.raw_value == 22.0
    assert result.calibrated_value == 20.5
    assert result.normalized_value == 20.5
    assert result.calibration_profile_id == f"{DEFAULT_TEMPLATE_KEY}:greenhouse.temperature-custom"
    assert result.normalization_profile_id == DEFAULT_TEMPLATE_KEY
    assert result.flags[ValidationFlag.RANGE] is False
    assert result.flags[ValidationFlag.VALID] is True
    assert result.dq_score == 1.0


def test_calibration_runs_before_range_validation(
    spark_session: SparkSession,
    base_config: dict[str, Any],
    tmp_path,
    configure_preprocess_db_client,
    sensor_registry,
) -> None:
    """Out-of-range raw values pass validation when calibration brings them into bounds."""
    sensors = register_sensors(sensor_registry, ["greenhouse.temperature"])
    sensor = sensors["greenhouse.temperature"]

    config = copy.deepcopy(base_config)
    config["sensors"]["greenhouse.temperature"]["calibration"] = {
        "strategy": "affine",
        "scale": 1.0,
        "offset": -2.0,
    }
    config_path = write_config(tmp_path, config)

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=sensor.plant_id,
            sensor_id=sensor.id,
            timestamp=base_time.timestamp(),
            value=31.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="calib-2",
        )
    ]

    processed = run_pipeline(spark_session, tmp_path, config_path, events)
    assert len(processed) == 1
    result = processed[0]
    assert result.imputed is False
    assert result.value == 29.0
    assert result.raw_value == 31.0
    assert result.calibrated_value == 29.0
    assert result.normalized_value == 29.0
    assert result.calibration_profile_id == f"{DEFAULT_TEMPLATE_KEY}:greenhouse.temperature-custom"
    assert result.normalization_profile_id == DEFAULT_TEMPLATE_KEY
    assert result.flags[ValidationFlag.RANGE] is False
    assert result.flags[ValidationFlag.VALID] is True
    assert result.dq_score == 1.0


def test_calibration_override_applies_via_registry_key(
    spark_session: SparkSession,
    base_config: dict[str, Any],
    tmp_path,
    configure_preprocess_db_client,
    sensor_registry,
) -> None:
    """Per-device overrides configured via registry key affect pipeline output."""
    override_key = "sensors.greenhouse.temperature.404"

    config = copy.deepcopy(base_config)
    config["sensors"][override_key] = {
        "template": DEFAULT_TEMPLATE_KEY,
        "calibration": {"strategy": "affine", "scale": 1.0, "offset": -2.5},
    }

    config_path = write_config(tmp_path, config)
    sensors = register_sensors(sensor_registry, [override_key])
    sensor = sensors[override_key]

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=sensor.plant_id,
            sensor_id=sensor.id,
            timestamp=base_time.timestamp(),
            value=24.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="calib-override",
        )
    ]

    processed = run_pipeline(spark_session, tmp_path, config_path, events)
    assert len(processed) == 1
    record = processed[0]
    assert record.imputed is False
    assert record.value == 21.5
    assert record.raw_value == 24.0
    assert record.calibrated_value == 21.5
    assert record.normalized_value == 21.5
    assert record.calibration_profile_id == f"{DEFAULT_TEMPLATE_KEY}:{override_key}-custom"
    assert record.normalization_profile_id == DEFAULT_TEMPLATE_KEY
    assert record.flags[ValidationFlag.RANGE] is False
    assert record.flags[ValidationFlag.VALID] is True
    assert record.dq_score == 1.0


def test_sensor_registry_configures_lookup(
    spark_session: SparkSession,
    base_config: dict[str, Any],
    tmp_path,
    configure_preprocess_db_client,
    sensor_registry,
) -> None:
    """Database-backed registry aligns sensor IDs with config entries."""
    config = copy.deepcopy(base_config)
    payload = config["sensors"].pop("greenhouse.temperature")
    config["sensors"]["plant.alpha"] = {
        **payload,
        "calibration": {"strategy": "affine", "scale": 1.0, "offset": -1.0},
    }
    config_path = write_config(tmp_path, config)

    sensors = register_sensors(sensor_registry, ["plant.alpha"])
    sensor = sensors["plant.alpha"]

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=sensor.plant_id,
            sensor_id=sensor.id,
            timestamp=base_time.timestamp(),
            value=23.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="registry-1",
        )
    ]

    processed = run_pipeline(spark_session, tmp_path, config_path, events)

    assert len(processed) == 1
    assert processed[0].sensor_id == sensor.id
    assert processed[0].value == 22.0
    assert processed[0].raw_value == 23.0
    assert processed[0].dq_score == 1.0
    assert processed[0].calibrated_value == 22.0
    assert processed[0].normalized_value == 22.0
    assert processed[0].calibration_profile_id == f"{DEFAULT_TEMPLATE_KEY}:plant.alpha-custom"
    assert processed[0].normalization_profile_id == DEFAULT_TEMPLATE_KEY


def test_unknown_sensor_is_skipped(
    spark_session: SparkSession,
    base_config: dict[str, Any],
    tmp_path,
    configure_preprocess_db_client,
    sensor_registry,
) -> None:
    """Unknown sensors are skipped when no registry mapping exists in config."""
    unknown_sensor_key = "greenhouse.humidity"
    sensors = register_sensors(sensor_registry, [unknown_sensor_key])
    sensor = sensors[unknown_sensor_key]
    config_path = write_config(tmp_path, base_config)

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=sensor.plant_id,
            sensor_id=sensor.id,
            timestamp=base_time.timestamp(),
            value=24.5,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="missing-registry",
        )
    ]

    processed = run_pipeline(spark_session, tmp_path, config_path, events)
    assert processed == []
