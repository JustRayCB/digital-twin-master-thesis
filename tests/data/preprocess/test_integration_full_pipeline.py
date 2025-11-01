import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pyspark.sql import Row, SparkSession

from dt.communication.dataclasses.processed_sensor_data import (
    ProcessedSensorData, ValidationFlag)
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics
from dt.data.preprocess.configuration.manager import ConfigurationManager
from dt.data.preprocess.spark_adapter import SparkStreamingAdapter


def _make_event(
    *,
    plant_id: int,
    sensor_id: int,
    timestamp: float,
    value: float,
    unit: str,
    topic: Topics,
    correlation_id: str,
) -> Row:
    """Create a RawSensorData-conformant row for streaming ingestion."""
    return Row(
        plant_id=int(plant_id),
        sensor_id=int(sensor_id),
        timestamp=float(timestamp),
        value=float(value),
        unit=str(unit),
        topic=topic.value,
        correlation_id=correlation_id,
    )


def _write_config_file(config_path: Path) -> str:
    """Return the string path for the provided config Path."""
    return str(config_path)


def _set_sensor_registry(mock_db_client, mapping: dict[int, str]) -> None:
    """Configure DatabaseApiClient mock to return the provided registry."""
    descriptors = [SimpleNamespace(sensor_id=sid, name=name) for sid, name in mapping.items()]
    mock_db_client.return_value.list_sensors.return_value = descriptors


def _run_streaming_batches(
    spark: SparkSession,
    config_path: str,
    batches: list[list[Row]],
    workspace: Path,
) -> list[ProcessedSensorData]:
    """Execute the modular pipeline against batches of raw events."""
    raw_schema = RawSensorData.get_spark_schema()

    input_dir = workspace / f"input_{uuid4().hex}"
    checkpoint_dir = workspace / f"chk_{uuid4().hex}"
    input_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    raw_stream = spark.readStream.format("parquet").schema(raw_schema).load(str(input_dir))

    config_manager = ConfigurationManager(config_path)
    adapter = SparkStreamingAdapter(config_manager)
    processed_stream = adapter.build_preprocessing_stream(spark, raw_stream)

    query_name = f"processed_{uuid4().hex}"
    query = (
        processed_stream.writeStream.format("memory")
        .queryName(query_name)
        .outputMode("update")
        .option("checkpointLocation", str(checkpoint_dir))
        .start()
    )

    try:
        for batch in batches:
            if not batch:
                continue
            df = spark.createDataFrame(batch, raw_schema)
            df.write.mode("append").format("parquet").save(str(input_dir))
            query.processAllAvailable()

        rows = spark.sql(f"SELECT * FROM {query_name}").collect()
        return [ProcessedSensorData.from_row(row) for row in rows]
    finally:
        query.stop()
        try:
            spark.catalog.dropTempView(query_name)
        except Exception:
            pass
        shutil.rmtree(input_dir, ignore_errors=True)
        shutil.rmtree(checkpoint_dir, ignore_errors=True)


def test_stream_pipeline_emits_valid_record(
    spark_session: SparkSession,
    test_config_path: str,
    mock_db_client,
    tmp_path: Path,
) -> None:
    """Valid reading should traverse the full Spark pipeline untouched."""
    _set_sensor_registry(mock_db_client, {101: "dht22.temperature"})
    config_path = _write_config_file(Path(test_config_path))

    timestamp = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
    events = [
        _make_event(
            plant_id=1,
            sensor_id=101,
            timestamp=timestamp,
            value=24.0,
            unit="°C",
            topic=Topics.TEMPERATURE,
            correlation_id="valid-1",
        )
    ]

    processed = _run_streaming_batches(spark_session, config_path, [events], tmp_path)
    assert len(processed) == 1
    record = processed[0]
    assert record.sensor_id == 101
    expected_calibrated = 24.0 * 1.05 - 0.5
    assert record.value == pytest.approx(expected_calibrated)
    assert record.flags[ValidationFlag.VALID] is True
    assert record.imputed is False
    assert record.normalized_value is not None
    assert record.calibration_profile_id is not None
    assert record.normalization_profile_id is not None


def test_stream_pipeline_imputes_invalid_reading(
    spark_session: SparkSession,
    test_config_path: str,
    mock_db_client,
    tmp_path: Path,
) -> None:
    """Out-of-range reading should be imputed using prior valid history."""
    _set_sensor_registry(mock_db_client, {101: "dht22.temperature"})
    config_path = _write_config_file(Path(test_config_path))

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    batches = [
        [
            _make_event(
                plant_id=1,
                sensor_id=101,
                timestamp=base_time.timestamp(),
                value=22.0,
                unit="°C",
                topic=Topics.TEMPERATURE,
                correlation_id="hist-1",
            ),
            _make_event(
                plant_id=1,
                sensor_id=101,
                timestamp=(base_time + timedelta(seconds=60)).timestamp(),
                value=200.0,
                unit="°C",
                topic=Topics.TEMPERATURE,
                correlation_id="invalid-1",
            ),
        ]
    ]

    processed = _run_streaming_batches(spark_session, config_path, batches, tmp_path)
    assert len(processed) == 2
    imputed = max(processed, key=lambda rec: rec.timestamp)
    assert imputed.flags[ValidationFlag.VALID] is False
    assert imputed.flags[ValidationFlag.RANGE] is True
    assert imputed.imputed is True
    expected_filled = 22.0 * 1.05 - 0.5
    assert imputed.value == pytest.approx(expected_filled)
    assert imputed.raw_value == pytest.approx(200.0)
    assert imputed.dq_score < 1.0


def test_stream_pipeline_keeps_state_unchanged_for_late_event(
    spark_session: SparkSession,
    test_config_path: str,
    mock_db_client,
    tmp_path: Path,
) -> None:
    """Late readings should not replace the last valid value in state."""
    _set_sensor_registry(mock_db_client, {101: "dht22.temperature"})
    config_path = _write_config_file(Path(test_config_path))

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    valid_batch = [
        _make_event(
            plant_id=1,
            sensor_id=101,
            timestamp=(base_time + timedelta(minutes=10)).timestamp(),
            value=21.5,
            unit="°C",
            topic=Topics.TEMPERATURE,
            correlation_id="future-1",
        )
    ]
    late_batch = [
        _make_event(
            plant_id=1,
            sensor_id=101,
            timestamp=(base_time + timedelta(minutes=5)).timestamp(),
            value=19.0,
            unit="°C",
            topic=Topics.TEMPERATURE,
            correlation_id="late-1",
        )
    ]
    invalid_batch = [
        _make_event(
            plant_id=1,
            sensor_id=101,
            timestamp=(base_time + timedelta(minutes=20)).timestamp(),
            value=150.0,
            unit="°C",
            topic=Topics.TEMPERATURE,
            correlation_id="invalid-2",
        )
    ]

    processed = _run_streaming_batches(
        spark_session, config_path, [valid_batch, late_batch, invalid_batch], tmp_path
    )

    assert len(processed) >= 2
    imputed = max(processed, key=lambda rec: rec.timestamp)
    assert imputed.flags[ValidationFlag.RANGE] is True
    assert imputed.imputed is True
    expected_baseline = 21.5 * 1.05 - 0.5
    assert imputed.value == pytest.approx(expected_baseline)


def test_stream_pipeline_emits_invalid_record_on_drop(
    spark_session: SparkSession,
    test_config_path: str,
    mock_db_client,
    tmp_path: Path,
) -> None:
    """When no history exists, irrecoverable readings surface as invalid outputs."""
    _set_sensor_registry(mock_db_client, {101: "dht22.temperature"})
    config_path = _write_config_file(Path(test_config_path))

    events = [
        _make_event(
            plant_id=1,
            sensor_id=101,
            timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp(),
            value=250.0,
            unit="°C",
            topic=Topics.TEMPERATURE,
            correlation_id="drop-1",
        )
    ]

    processed = _run_streaming_batches(spark_session, config_path, [events], tmp_path)
    assert len(processed) == 1
    record = processed[0]
    assert record.flags[ValidationFlag.VALID] is False
    assert record.flags[ValidationFlag.RANGE] is True
    assert record.imputed is False
    assert record.dq_score == 0.0
    expected_calibrated = 250.0 * 1.05 - 0.5
    assert record.value == pytest.approx(expected_calibrated)
