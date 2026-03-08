from datetime import datetime, timezone
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics
from dt.data.preprocess.config.manager import ConfigurationManager
from dt.data.preprocess.spark_adapter import PROCESSED_EVENT_COLUMNS, SparkStreamingAdapter
from tests.data.preprocess.pipeline.pipeline_runner import make_event


def _write_stream_source(
    spark_session: SparkSession, workspace: Path, events
):
    input_dir = workspace / "spark_adapter_input"
    input_dir.mkdir(parents=True, exist_ok=True)

    raw_schema = RawSensorData.get_spark_schema()
    spark_session.createDataFrame(events, raw_schema).write.mode("overwrite").parquet(
        str(input_dir)
    )
    return spark_session.readStream.schema(raw_schema).parquet(str(input_dir))


def _collect_stream_rows(
    spark_session: SparkSession,
    processed_stream,
    checkpoint_dir: Path,
    query_name: str,
):
    query = (
        processed_stream.writeStream.format("memory")
        .queryName(query_name)
        .outputMode("update")
        .option("checkpointLocation", str(checkpoint_dir))
        .start()
    )

    try:
        query.processAllAvailable()
        return spark_session.sql(f"SELECT * FROM {query_name}").collect()
    finally:
        query.stop()
        try:
            spark_session.catalog.dropTempView(query_name)
        except Exception:
            pass


def test_setup_watermark_applies_event_time(
    spark_session: SparkSession,
    tmp_path,
    test_config_path,
    configure_preprocess_db_client,
) -> None:
    """setup_watermark adds event_time to streaming input."""
    adapter = SparkStreamingAdapter(ConfigurationManager(test_config_path))

    raw_events = _write_stream_source(
        spark_session,
        tmp_path,
        [
            make_event(
                plant_id=1,
                sensor_id=101,
                timestamp=1609459200.0,
                value=25.0,
                unit="°C",
                topic=Topics.TEMPERATURE,
                correlation_id="corr-1",
            )
        ],
    )

    result = adapter.setup_watermark(raw_events, "45 minutes")

    assert result.isStreaming
    assert "event_time" in result.columns
    assert "timestamp" in result.columns
    assert "plant_id" in result.columns


def test_setup_watermark_requires_streaming_input(
    spark_session: SparkSession,
    test_config_path,
    configure_preprocess_db_client,
) -> None:
    """setup_watermark rejects non-streaming inputs."""
    adapter = SparkStreamingAdapter(ConfigurationManager(test_config_path))
    raw_schema = RawSensorData.get_spark_schema()
    raw_events = spark_session.createDataFrame([], raw_schema)

    with pytest.raises(ValueError, match="requires a streaming DataFrame"):
        adapter.setup_watermark(raw_events, "30 minutes")


def test_build_preprocessing_stream_requires_streaming_input(
    spark_session: SparkSession,
    test_config_path,
    configure_preprocess_db_client,
) -> None:
    """build_preprocessing_stream rejects non-streaming inputs."""
    adapter = SparkStreamingAdapter(ConfigurationManager(test_config_path))
    raw_schema = RawSensorData.get_spark_schema()
    raw_events = spark_session.createDataFrame([], raw_schema)

    with pytest.raises(ValueError, match="requires a streaming DataFrame"):
        adapter.build_preprocessing_stream(spark_session, raw_events)


def test_build_preprocessing_stream_emits_processed_rows(
    spark_session: SparkSession,
    tmp_path,
    test_config_path,
    configure_preprocess_db_client,
    sensor_registry,
) -> None:
    """Streaming adapter should emit processed records for known sensors."""
    sensor = sensor_registry["register"]("dht22.temperature")

    adapter = SparkStreamingAdapter(ConfigurationManager(test_config_path))
    raw_events = _write_stream_source(
        spark_session,
        tmp_path,
        [
            make_event(
                plant_id=sensor.plant_id,
                sensor_id=sensor.id,
                timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp(),
                value=24.0,
                unit="°C",
                topic=Topics.TEMPERATURE,
                correlation_id="adapter-1",
            )
        ],
    )

    processed_stream = adapter.build_preprocessing_stream(spark_session, raw_events)
    assert processed_stream.columns == list(PROCESSED_EVENT_COLUMNS)

    checkpoint_dir = tmp_path / "adapter_checkpoint"
    query_name = "adapter_results"
    rows = _collect_stream_rows(
        spark_session,
        processed_stream,
        checkpoint_dir,
        query_name,
    )
    assert len(rows) == 1
    record = rows[0].asDict()
    assert record["sensor_id"] == sensor.id
    assert record["raw_value"] == 24.0
    assert record["flags"][ValidationFlag.VALID.value] is True


def test_build_preprocessing_stream_skips_unknown_sensors(
    spark_session: SparkSession,
    tmp_path,
    test_config_path,
    configure_preprocess_db_client,
) -> None:
    """Streaming adapter skips readings with no registry entry."""
    adapter = SparkStreamingAdapter(ConfigurationManager(test_config_path))
    raw_events = _write_stream_source(
        spark_session,
        tmp_path,
        [
            make_event(
                plant_id=1,
                sensor_id=9999,
                timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp(),
                value=22.0,
                unit="°C",
                topic=Topics.TEMPERATURE,
                correlation_id="adapter-unknown-1",
            )
        ],
    )

    processed_stream = adapter.build_preprocessing_stream(spark_session, raw_events)
    checkpoint_dir = tmp_path / "adapter_checkpoint_unknown"
    query_name = "adapter_results_unknown"
    rows = _collect_stream_rows(
        spark_session,
        processed_stream,
        checkpoint_dir,
        query_name,
    )
    assert len(rows) == 0


def test_build_preprocessing_stream_emits_invalid_record_when_imputation_drops(
    spark_session: SparkSession,
    tmp_path,
    test_config_path,
    configure_preprocess_db_client,
    sensor_registry,
) -> None:
    """Streaming adapter emits invalid record when imputation cannot recover."""
    sensor = sensor_registry["register"]("dht22.temperature")

    adapter = SparkStreamingAdapter(ConfigurationManager(test_config_path))
    raw_events = _write_stream_source(
        spark_session,
        tmp_path,
        [
            make_event(
                plant_id=sensor.plant_id,
                sensor_id=sensor.id,
                timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp(),
                value=200.0,
                unit="°C",
                topic=Topics.TEMPERATURE,
                correlation_id="adapter-drop-1",
            )
        ],
    )

    processed_stream = adapter.build_preprocessing_stream(spark_session, raw_events)
    checkpoint_dir = tmp_path / "adapter_checkpoint_drop"
    query_name = "adapter_results_drop"
    rows = _collect_stream_rows(
        spark_session,
        processed_stream,
        checkpoint_dir,
        query_name,
    )
    assert len(rows) == 1
    record = rows[0].asDict()
    assert record["sensor_id"] == sensor.id
    assert record["flags"][ValidationFlag.VALID.value] is False
    assert record["flags"][ValidationFlag.RANGE.value] is True
    assert record["dq_score"] == 0.0
