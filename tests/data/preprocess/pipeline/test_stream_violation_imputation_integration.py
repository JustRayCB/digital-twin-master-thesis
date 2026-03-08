import copy
from datetime import datetime, timedelta, timezone
from typing import Any

from pyspark.sql import SparkSession

from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.topics import Topics

from tests.data.preprocess.pipeline.pipeline_runner import (
    DEFAULT_TEMPLATE_KEY,
    make_event,
    register_sensors,
    run_pipeline,
)


def test_range_violation_triggers_imputation(
    spark_session: SparkSession,
    base_config: dict[str, Any],
    tmp_path,
    config_writer,
    configure_preprocess_db_client,
    sensor_registry,
) -> None:
    """Out-of-range readings are imputed using the last valid reading."""
    sensors = register_sensors(sensor_registry, ["greenhouse.temperature"])
    sensor = sensors["greenhouse.temperature"]
    config_path = config_writer(base_config)

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=sensor.plant_id,
            sensor_id=sensor.id,
            timestamp=base_time.timestamp(),
            value=21.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="c-1",
        ),
        make_event(
            plant_id=sensor.plant_id,
            sensor_id=sensor.id,
            timestamp=(base_time + timedelta(seconds=30)).timestamp(),
            value=45.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="c-2",
        ),
    ]

    processed = run_pipeline(spark_session, tmp_path, config_path, events)
    assert processed[-1].imputed is True
    assert processed[-1].value == 21.0
    assert processed[-1].flags[ValidationFlag.RANGE] is True
    assert processed[-1].flags[ValidationFlag.RATE_OF_CHANGE] is False
    assert processed[-1].flags[ValidationFlag.STUCK] is False
    assert processed[-1].dq_score == 0.5
    assert processed[-1].raw_value == 45.0
    assert processed[-1].calibrated_value == 45.0
    assert processed[-1].normalized_value == 21.0
    assert processed[-1].calibration_profile_id == DEFAULT_TEMPLATE_KEY
    assert processed[-1].normalization_profile_id == DEFAULT_TEMPLATE_KEY


def test_range_violation_without_history_emits_dropped_record(
    spark_session: SparkSession,
    base_config: dict[str, Any],
    tmp_path,
    config_writer,
    configure_preprocess_db_client,
    sensor_registry,
) -> None:
    """Range violations without history emit an invalid record instead of imputing."""
    sensors = register_sensors(sensor_registry, ["greenhouse.temperature"])
    sensor = sensors["greenhouse.temperature"]
    config_path = config_writer(base_config)

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=sensor.plant_id,
            sensor_id=sensor.id,
            timestamp=base_time.timestamp(),
            value=45.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="drop-1",
        ),
    ]

    processed = run_pipeline(spark_session, tmp_path, config_path, events)

    assert len(processed) == 1
    record = processed[0]
    assert record.value == 45.0
    assert record.raw_value == 45.0
    assert record.flags[ValidationFlag.RANGE] is True
    assert record.flags[ValidationFlag.VALID] is False
    assert record.imputed is False
    assert record.dq_score == 0.0
    assert record.calibrated_value == 45.0
    assert record.normalized_value is None
    assert record.calibration_profile_id == DEFAULT_TEMPLATE_KEY
    assert record.normalization_profile_id == DEFAULT_TEMPLATE_KEY


def test_rate_of_change_violation_triggers_imputation(
    spark_session: SparkSession,
    base_config: dict[str, Any],
    tmp_path,
    config_writer,
    configure_preprocess_db_client,
    sensor_registry,
) -> None:
    """Excessive rate-of-change violations are imputed using the last valid reading."""
    sensors = register_sensors(sensor_registry, ["greenhouse.temperature"])
    sensor = sensors["greenhouse.temperature"]

    config = copy.deepcopy(base_config)
    config["templates"][DEFAULT_TEMPLATE_KEY]["validation"]["roc"] = {"max_per_minute": 1.0}
    config_path = config_writer(config)

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=sensor.plant_id,
            sensor_id=sensor.id,
            timestamp=base_time.timestamp(),
            value=20.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="roc-1",
        ),
        make_event(
            plant_id=sensor.plant_id,
            sensor_id=sensor.id,
            timestamp=(base_time + timedelta(seconds=30)).timestamp(),
            value=25.5,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="roc-2",
        ),
    ]

    processed = run_pipeline(spark_session, tmp_path, config_path, events)
    assert processed[-1].imputed is True
    assert processed[-1].value == 20.0
    assert processed[-1].flags[ValidationFlag.RATE_OF_CHANGE] is True
    assert processed[-1].flags[ValidationFlag.RANGE] is False
    assert processed[-1].flags[ValidationFlag.STUCK] is False
    assert processed[-1].dq_score == 0.7
    assert processed[-1].raw_value == 25.5
    assert processed[-1].calibrated_value == 25.5
    assert processed[-1].normalized_value == 20.0
    assert processed[-1].calibration_profile_id == DEFAULT_TEMPLATE_KEY
    assert processed[-1].normalization_profile_id == DEFAULT_TEMPLATE_KEY


def test_stuck_detection_flags_flatline(
    spark_session: SparkSession,
    base_config: dict[str, Any],
    tmp_path,
    config_writer,
    configure_preprocess_db_client,
    sensor_registry,
) -> None:
    """Flatlined values beyond the configured window are flagged and imputed."""
    sensors = register_sensors(sensor_registry, ["greenhouse.temperature"])
    sensor = sensors["greenhouse.temperature"]

    config = copy.deepcopy(base_config)
    config["templates"][DEFAULT_TEMPLATE_KEY]["validation"]["stuck"] = {"max_flat_seconds": 30}
    config_path = config_writer(config)

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=sensor.plant_id,
            sensor_id=sensor.id,
            timestamp=(base_time + timedelta(seconds=offset)).timestamp(),
            value=19.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id=f"stuck-{offset}",
        )
        for offset in (0, 15, 45)
    ]

    processed = run_pipeline(spark_session, tmp_path, config_path, events)
    assert processed[-1].flags[ValidationFlag.STUCK] is True
    assert processed[-1].imputed is True
    assert processed[-1].value == 19.0
    assert processed[-1].dq_score == 0.8
    assert processed[-1].raw_value == 19.0
    assert processed[-1].calibrated_value == 19.0
    assert processed[-1].normalized_value == 19.0
    assert processed[-1].calibration_profile_id == DEFAULT_TEMPLATE_KEY
    assert processed[-1].normalization_profile_id == DEFAULT_TEMPLATE_KEY


def test_valid_reading_passes_through(
    spark_session: SparkSession,
    base_config: dict[str, Any],
    tmp_path,
    config_writer,
    configure_preprocess_db_client,
    sensor_registry,
) -> None:
    """Valid readings pass with full score and no imputation."""
    sensors = register_sensors(sensor_registry, ["greenhouse.temperature"])
    sensor = sensors["greenhouse.temperature"]
    config_path = config_writer(base_config)

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=sensor.plant_id,
            sensor_id=sensor.id,
            timestamp=base_time.timestamp(),
            value=22.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="ok-1",
        )
    ]

    processed = run_pipeline(spark_session, tmp_path, config_path, events)
    assert len(processed) == 1
    result = processed[0]
    assert result.imputed is False
    assert result.value == 22.0
    assert result.flags[ValidationFlag.RANGE] is False
    assert result.flags[ValidationFlag.RATE_OF_CHANGE] is False
    assert result.flags[ValidationFlag.STUCK] is False
    assert result.flags[ValidationFlag.VALID] is True
    assert result.dq_score == 1.0
    assert result.raw_value == 22.0
    assert result.calibrated_value == 22.0
    assert result.normalized_value == 22.0
    assert result.calibration_profile_id == DEFAULT_TEMPLATE_KEY
    assert result.normalization_profile_id == DEFAULT_TEMPLATE_KEY
