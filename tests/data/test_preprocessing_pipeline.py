import copy
import math
import shutil
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest
import yaml
from pyspark.sql import DataFrame, Row, SparkSession

from dt.communication.dataclasses import ProcessedSensorData
from dt.communication.dataclasses.preprocessing_config import (
    ForwardFillImputationConfig, RangeConfig, RocConfig, SensorConfig,
    StuckConfig)
from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics
from dt.data.preprocess import pipeline as preprocess_main
from dt.data.preprocess import validators
from dt.data.preprocess.dq import compute_dq_score
from dt.data.preprocess.imputers import build_strategy
from dt.data.preprocess.pipeline import build_preprocessing_stream
from dt.data.preprocess.state import FlatlineRecord, StateProvider


@pytest.fixture(scope="module")
def spark_session():
    """Create a Spark session for integration-style streaming tests."""
    session = (
        SparkSession.builder.master("local[*]")
        .appName("preprocessing-pipeline-tests")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


@pytest.fixture
def base_config() -> dict[str, Any]:
    """Provide a reusable preprocessing configuration for sensor validation tests.

    Returns
    -------
    dict[str, Any]
        Configuration with default scoring weights and validator thresholds.
    """
    return {
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
            "greenhouse.temperature": {
                "units": "C",
                "range": {"min": 10.0, "max": 30.0},
                "roc": {"max_per_minute": 2.5},
                "stuck": {"max_flat_seconds": 120},
            }
        },
    }


@pytest.fixture(autouse=True)
def stub_sensor_registry(monkeypatch) -> None:
    """Avoid network calls when the pipeline tries to fetch sensor descriptors."""

    mapping = {sid: "greenhouse.temperature" for sid in (101, 202, 303, 404)}
    monkeypatch.setattr(
        preprocess_main,
        "_load_sensor_registry",
        lambda rules, _mapping=mapping: dict(_mapping),
    )


def write_config(tmp_path, config) -> str:
    """Persist the provided configuration to disk for pipeline tests.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Temporary directory fixture supplied by pytest.
    config : dict[str, Any]
        Preprocessing configuration to serialise.

    Returns
    -------
    str
        File system path to the emitted YAML configuration file.
    """
    config_path = tmp_path / "preprocess_config.yml"
    config_path.write_text(yaml.safe_dump(config))
    return str(config_path)


def make_event(
    plant_id: int,
    sensor_id: int,
    timestamp: float,
    value: float,
    unit: str,
    topic: Topics,
    correlation_id: str,
) -> Row:
    """Construct a raw sensor Row compatible with the preprocessing schema.

    Parameters
    ----------
    plant_id : int
        Identifier for the greenhouse plant the sensor belongs to.
    sensor_id : int
        Unique sensor identifier within the plant.
    timestamp : float
        Event epoch timestamp in seconds.
    value : float
        Sensor reading captured at `timestamp`.
    unit : str
        Physical unit associated with the reading.
    topic : Topics
        Kafka topic enum describing the sensor stream.
    correlation_id : str
        Identifier used for tracing events end-to-end.

    Returns
    -------
    pyspark.sql.Row
        Row matching `RawSensorData.get_spark_schema()`, ready for DataFrame ingestion.
    """
    return Row(
        plant_id=int(plant_id),
        sensor_id=int(sensor_id),
        timestamp=float(timestamp),
        value=float(value),
        unit=unit,
        topic=topic.value,
        correlation_id=correlation_id,
    )


def run_pipeline(
    spark: SparkSession,
    tmp_path,
    config_path: str,
    events: list[Row],
) -> list[ProcessedSensorData]:
    """Execute the preprocessing transform against synthetic raw events.

    Parameters
    ----------
    spark : pyspark.sql.SparkSession
        Spark session to execute the pipeline.
    tmp_path : pathlib.Path
        Temporary directory for staging streaming input/output.
    config_path : str
        Path to the preprocessing configuration YAML.
    events : list[Row]
        Initial batch of raw events to feed the stream.
    """

    # 1. Prepare streaming source (write test parquet files)
    input_dir = tmp_path / f"stream_input_{uuid4().hex}"
    input_dir.mkdir(parents=True, exist_ok=True)

    (
        spark.createDataFrame(events, RawSensorData.get_spark_schema())
        .write.mode("overwrite")
        .format("parquet")
        .save(str(input_dir))
    )
    raw_stream = (
        spark.readStream.format("parquet")
        .schema(RawSensorData.get_spark_schema())
        .load(str(input_dir))
    )

    # 2. Build processing plan
    processed_stream: DataFrame = build_preprocessing_stream(
        spark_session=spark, raw_events=raw_stream, config_path=config_path
    )
    # 3. Start query with memory sink so we can inspect results
    query_name = f"processed_{uuid4().hex}"
    checkpoint = tmp_path / f"chk_{uuid4().hex}"
    checkpoint.mkdir()
    query = (
        processed_stream.writeStream.format("memory")
        .queryName(query_name)
        .outputMode("update")
        .option("checkpointLocation", str(checkpoint))
        .start()
    )
    try:
        # 4–5. Trigger micro-batch and wait for completion
        query.processAllAvailable()

        # 6. Collect results from the in-memory table
        rows = spark.sql(f"SELECT * FROM {query_name}").collect()
        return [ProcessedSensorData.from_row(row) for row in rows]
    finally:
        query.stop()
        spark.catalog.dropTempView(query_name)
        shutil.rmtree(checkpoint, ignore_errors=True)


def test_range_violation_triggers_imputation(
    spark_session: SparkSession, base_config: dict[str, Any], tmp_path
) -> None:
    """Ensure an out-of-range reading is imputed and flagged accordingly.

    Parameters
    ----------
    spark_session : pyspark.sql.SparkSession
        Local Spark session used to execute the preprocessing transform.
    base_config : dict[str, Any]
        Default preprocessing configuration for validator thresholds.
    tmp_path : pathlib.Path
        Temporary directory where the test-specific config file is written.
    """
    config_path = write_config(tmp_path, base_config)
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=1,
            sensor_id=101,
            timestamp=base_time.timestamp(),
            value=21.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="c-1",
        ),
        make_event(
            plant_id=1,
            sensor_id=101,
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


def test_rate_of_change_violation_triggers_imputation(
    spark_session: SparkSession, base_config: dict[str, Any], tmp_path
) -> None:
    """Verify excessive rate-of-change triggers violation flags and imputation.

    Parameters
    ----------
    spark_session : pyspark.sql.SparkSession
        Local Spark session used to execute the preprocessing transform.
    base_config : dict[str, Any]
        Baseline preprocessing configuration before ROC overrides.
    tmp_path : pathlib.Path
        Temporary directory storing the per-test YAML configuration.
    """
    config = copy.deepcopy(base_config)
    config["sensors"]["greenhouse.temperature"]["roc"] = {"max_per_minute": 1.0}
    config_path = write_config(tmp_path, config)
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=1,
            sensor_id=202,
            timestamp=base_time.timestamp(),
            value=20.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="roc-1",
        ),
        make_event(
            plant_id=1,
            sensor_id=202,
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


def test_stuck_detection_flags_flatline(
    spark_session: SparkSession, base_config: dict[str, Any], tmp_path
) -> None:
    """Confirm flatlined readings beyond the window raise stuck flags and impute.

    Parameters
    ----------
    spark_session : pyspark.sql.SparkSession
        Local Spark session used to execute the preprocessing transform.
    base_config : dict[str, Any]
        Baseline preprocessing configuration before stuck overrides.
    tmp_path : pathlib.Path
        Temporary directory storing the test-specific configuration YAML.
    """
    config = copy.deepcopy(base_config)
    config["sensors"]["greenhouse.temperature"]["stuck"] = {"max_flat_seconds": 30}
    config_path = write_config(tmp_path, config)
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=1,
            sensor_id=303,
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


def test_violation_without_history_does_not_impute(
    spark_session: SparkSession, base_config: dict[str, Any], tmp_path
) -> None:
    """Range violation without history should still surface a violation without imputation."""

    config_path = write_config(tmp_path, base_config)
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=1,
            sensor_id=101,
            timestamp=base_time.timestamp(),
            value=60.0,  # immediately out of bounds
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="range-alone",
        )
    ]

    processed = run_pipeline(spark_session, tmp_path, config_path, events)
    assert len(processed) == 1
    record = processed[0]
    assert record.imputed is False
    assert record.flags[ValidationFlag.RANGE] is True
    assert record.dq_score == 0.5
    assert record.raw_value is None


def test_valid_reading_passes_through(
    spark_session: SparkSession, base_config: dict[str, Any], tmp_path
) -> None:
    """Check that a well-behaved reading passes untouched with full score.

    Parameters
    ----------
    spark_session : pyspark.sql.SparkSession
        Local Spark session used to execute the preprocessing transform.
    base_config : dict[str, Any]
        Default preprocessing configuration used without overrides.
    tmp_path : pathlib.Path
        Temporary directory for the configuration YAML written by the test.
    """
    config_path = write_config(tmp_path, base_config)
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=2,
            sensor_id=404,
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
    assert result.raw_value is None


def test_sensor_registry_configures_lookup(
    spark_session: SparkSession,
    base_config: dict[str, Any],
    tmp_path,
    monkeypatch,
) -> None:
    """Database-backed registry should align sensor IDs with config entries."""

    config = copy.deepcopy(base_config)
    payload = config["sensors"].pop("greenhouse.temperature")
    config["sensors"]["plant.alpha"] = payload
    monkeypatch.setattr(
        preprocess_main,
        "_load_sensor_registry",
        lambda rules: {909: "plant.alpha"},
    )
    config_path = write_config(tmp_path, config)
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=5,
            sensor_id=909,
            timestamp=base_time.timestamp(),
            value=23.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="registry-1",
        )
    ]

    processed = run_pipeline(spark_session, tmp_path, config_path, events)

    assert len(processed) == 1
    assert processed[0].sensor_id == 909
    assert processed[0].value == 23.0
    assert processed[0].raw_value is None
    assert processed[0].dq_score == 1.0


def test_unknown_sensor_is_skipped(
    spark_session: SparkSession,
    base_config: dict[str, Any],
    tmp_path,
    monkeypatch,
) -> None:
    """Pipeline should emit quarantine record instead of crashing on unknown sensors."""

    monkeypatch.setattr(preprocess_main, "_load_sensor_registry", lambda rules: {})
    config_path = write_config(tmp_path, base_config)
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    events = [
        make_event(
            plant_id=9,
            sensor_id=999,
            timestamp=base_time.timestamp(),
            value=24.5,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id="missing-registry",
        )
    ]

    processed = run_pipeline(spark_session, tmp_path, config_path, events)

    assert processed == []


def test_dq_score_respects_config_weights(base_config: dict[str, Any]) -> None:
    """Validate the data-quality score honours configured validation weights.

    Parameters
    ----------
    base_config : dict[str, Any]
        Baseline preprocessing configuration supplying scoring weights.
    """
    weights = base_config["defaults"]["scoring"]["weights"]
    flags = {
        ValidationFlag.RANGE: False,
        ValidationFlag.RATE_OF_CHANGE: True,
        ValidationFlag.STUCK: True,
    }
    score = compute_dq_score(flags, weights)
    assert score == weights["range_ok"]


def test_dq_score_returns_full_weight_when_all_checks_pass(base_config: dict[str, Any]) -> None:
    """Ensure the score reaches 1.0 when every validation passes."""

    weights = base_config["defaults"]["scoring"]["weights"]
    flags = {
        ValidationFlag.RANGE: False,
        ValidationFlag.RATE_OF_CHANGE: False,
        ValidationFlag.STUCK: False,
    }

    score = compute_dq_score(flags, weights)
    assert score == 1.0


def test_dq_score_drops_to_zero_when_all_checks_fail(base_config: dict[str, Any]) -> None:
    """Confirm the weighted score collapses to zero on complete failure."""

    weights = base_config["defaults"]["scoring"]["weights"]
    flags = {
        ValidationFlag.RANGE: True,
        ValidationFlag.RATE_OF_CHANGE: True,
        ValidationFlag.STUCK: True,
    }

    score = compute_dq_score(flags, weights)
    assert score == 0.0


def test_dq_score_handles_missing_weights() -> None:
    """Score should degrade gracefully when weight keys are absent."""

    weights: dict[str, float] = {}
    flags = {
        ValidationFlag.RANGE: False,
        ValidationFlag.RATE_OF_CHANGE: True,
        ValidationFlag.STUCK: False,
    }

    score = compute_dq_score(flags, weights)
    assert score == 0.0


def test_check_range_flags_out_of_bounds_value() -> None:
    """Range validator rejects values falling outside configured bounds."""
    rule = RangeConfig(min=10.0, max=30.0)
    reading = RawSensorData(
        plant_id=1,
        sensor_id=10,
        timestamp=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc).timestamp(),
        value=35.0,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="range-ok",
    )
    is_valid, reason = validators.check_range(reading=reading, rule=rule)
    assert is_valid is False
    assert reason is ValidationFlag.RANGE


def test_check_range_accepts_value_within_bounds() -> None:
    """Range validator accepts values located inside configured bounds."""
    reading = RawSensorData(
        plant_id=1,
        sensor_id=10,
        timestamp=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc).timestamp(),
        value=25.0,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="range-ok",
    )

    rule = RangeConfig(min=10.0, max=30.0)
    is_valid, reason = validators.check_range(reading=reading, rule=rule)
    assert is_valid is True
    assert reason is ValidationFlag.VALID


def test_check_rate_of_change_flags_excessive_delta() -> None:
    """Rate-of-change validator flags deltas exceeding the configured limit."""
    rule = RocConfig(max_per_minute=2.0, profiles={}, active_profile=None)
    previous = RawSensorData(
        plant_id=1,
        sensor_id=10,
        timestamp=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc).timestamp(),
        value=20.0,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="roc-prev",
    )
    reading = RawSensorData(
        plant_id=1,
        sensor_id=10,
        timestamp=datetime(2025, 1, 1, 12, 0, 30, tzinfo=timezone.utc).timestamp(),
        value=26.0,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="roc-read",
    )
    is_valid, reason = validators.check_rate_of_change(
        reading=reading, previous_valid=previous, rule=rule
    )
    assert is_valid is False
    assert reason is ValidationFlag.RATE_OF_CHANGE


def test_check_rate_of_change_accepts_delta_within_limit() -> None:
    """Rate-of-change validator approves deltas inside the configured limit."""
    rule = RocConfig(max_per_minute=4.0, profiles={}, active_profile=None)
    previous = RawSensorData(
        plant_id=1,
        sensor_id=11,
        timestamp=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc).timestamp(),
        value=20.0,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="roc-prev-ok",
    )
    reading = RawSensorData(
        plant_id=1,
        sensor_id=11,
        timestamp=datetime(2025, 1, 1, 12, 0, 30, tzinfo=timezone.utc).timestamp(),
        value=21.5,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="roc-read-ok",
    )
    is_valid, reason = validators.check_rate_of_change(
        reading=reading, previous_valid=previous, rule=rule
    )
    assert is_valid is True
    assert reason is ValidationFlag.VALID


def test_check_stuck_flags_flatline_beyond_threshold() -> None:
    """Stuck validator identifies flatlined windows exceeding the threshold."""
    rule = StuckConfig(max_flat_seconds=45)
    base_time = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    history = [
        RawSensorData(
            plant_id=1,
            sensor_id=12,
            timestamp=(base_time + timedelta(seconds=offset)).timestamp(),
            value=18.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id=f"stuck-{offset}",
        )
        for offset in (0, 30, 60)
    ]
    is_valid, reason = validators.check_stuck(history=history, rule=rule)
    assert is_valid is False
    assert reason is ValidationFlag.STUCK


def test_check_stuck_accepts_varying_values() -> None:
    """Stuck validator passes windows with sufficient movement."""
    rule = StuckConfig(max_flat_seconds=45)
    base_time = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    history = [
        RawSensorData(
            plant_id=1,
            sensor_id=13,
            timestamp=(base_time + timedelta(seconds=offset)).timestamp(),
            value=18.0 + (offset / 100),
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id=f"stuck-ok-{offset}",
        )
        for offset in (0, 30, 60)
    ]
    is_valid, reason = validators.check_stuck(history=history, rule=rule)
    assert is_valid is True
    assert reason is ValidationFlag.VALID


class _ImputationState(StateProvider):
    """Minimal state adapter for imputation behaviour checks."""

    def __init__(self) -> None:
        self._last_valid: dict[int, RawSensorData] = {}
        self._flatline: dict[int, FlatlineRecord] = {}
        self._history: dict[int, list[RawSensorData]] = {}

    def get_last_valid(self, sensor_id: int) -> RawSensorData | None:
        return self._last_valid.get(sensor_id)

    def update(self, sensor_id: int, reading: RawSensorData) -> None:
        self._last_valid[sensor_id] = reading
        self._history.setdefault(sensor_id, []).append(reading)

    def record_flatline(self, sensor_id: int, value: float, timestamp: float) -> None:
        self._flatline[sensor_id] = FlatlineRecord(value=value, timestamp=timestamp)

    def get_flatline(self, sensor_id: int) -> FlatlineRecord | None:
        return self._flatline.get(sensor_id)

    def get_recent_history(
        self, sensor_id: int, window_seconds: float, reference_timestamp: float
    ) -> list[RawSensorData]:
        history = self._history.get(sensor_id, [])
        cutoff = reference_timestamp - window_seconds
        return [row for row in history if row.timestamp >= cutoff]


def test_imputation_decay_applies_for_moderate_gap() -> None:
    """Forward fill strategy should decay toward baseline when the gap widens."""
    sensor_config = SensorConfig(
        units="C",
        range=RangeConfig(min=10.0, max=30.0),
        roc=RocConfig(max_per_minute=2.0, profiles={}, active_profile=None),
        stuck=StuckConfig(max_flat_seconds=120),
        imputation=ForwardFillImputationConfig(
            max_gap_seconds=300,
            decay_seconds=120,
            baseline=18.0,
        ),
    )
    strategy = build_strategy(sensor_config=sensor_config)
    state = _ImputationState()
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
    last_valid = RawSensorData(
        plant_id=1,
        sensor_id=501,
        timestamp=base_time,
        value=22.0,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="imp-1",
    )
    state.update(sensor_id=last_valid.sensor_id, reading=last_valid)
    reading = RawSensorData(
        plant_id=1,
        sensor_id=501,
        timestamp=base_time + 150,
        value=5.0,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="imp-2",
    )

    imputed_value = strategy.compute(sensor_id=reading.sensor_id, reading=reading, state=state)

    expected = 18.0 + (22.0 - 18.0) * math.exp(-150 / 120)
    assert imputed_value is not None
    assert imputed_value == expected


def test_imputation_returns_baseline_beyond_max_gap() -> None:
    """Strategy falls back to baseline when the gap exceeds configured limit."""
    sensor_config = SensorConfig(
        units="C",
        range=RangeConfig(min=10.0, max=30.0),
        roc=RocConfig(max_per_minute=2.0, profiles={}, active_profile=None),
        stuck=StuckConfig(max_flat_seconds=120),
        imputation=ForwardFillImputationConfig(
            max_gap_seconds=180,
            decay_seconds=60,
            baseline=17.5,
        ),
    )
    strategy = build_strategy(sensor_config=sensor_config)
    state = _ImputationState()
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
    last_valid = RawSensorData(
        plant_id=1,
        sensor_id=777,
        timestamp=base_time,
        value=23.0,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="imp-gap-1",
    )
    state.update(sensor_id=last_valid.sensor_id, reading=last_valid)
    reading = RawSensorData(
        plant_id=1,
        sensor_id=777,
        timestamp=base_time + 600,
        value=5.0,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="imp-gap-2",
    )

    imputed_value = strategy.compute(sensor_id=reading.sensor_id, reading=reading, state=state)

    assert imputed_value is not None
    assert imputed_value == 17.5
