from datetime import datetime, timezone
from typing import Any, Iterator
from unittest.mock import Mock

import pandas as pd
import pytest
from pyspark.sql.streaming.state import GroupStateTimeout

from dt.communication.dataclasses.processed_sensor_data import (
    ProcessedSensorData, ValidationFlag)
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.data.preprocess.state import SensorState
from dt.communication.topics import Topics
from dt.data.preprocess.configuration.manager import ConfigurationManager
from dt.data.preprocess.spark_adapter import (
    PROCESSED_EVENT_COLUMNS,
    SparkStreamingAdapter,
)
from dt.data.preprocess.state import SparkStateProvider


@pytest.fixture
def config_manager(test_config_path):
    """Create a real ConfigurationManager with test config."""
    return ConfigurationManager(test_config_path)


@pytest.fixture
def spark_adapter(config_manager):
    """Provide a SparkStreamingAdapter with real config manager."""
    return SparkStreamingAdapter(config_manager)


def _make_group_state(has_timed_out: bool = False, watermark_ms: int = 0) -> Mock:
    """Create a minimal GroupState mock."""
    group_state = Mock()
    group_state.hasTimedOut = has_timed_out
    group_state.exists = False
    group_state.get = None
    group_state.getCurrentWatermarkMs.return_value = watermark_ms
    group_state.remove = Mock()
    group_state.update = Mock()
    group_state.setTimeoutTimestamp = Mock()
    return group_state


def _make_dataframe(values: list[dict[str, Any]]) -> pd.DataFrame:
    """Create a pandas DataFrame matching RawSensorData schema."""
    return pd.DataFrame(values)


def test_setup_watermark_applies_event_time(spark_session, tmp_path) -> None:
    """Test that setup_watermark applies proper event time transformation."""
    config_manager = Mock()
    adapter = SparkStreamingAdapter(config_manager)

    # Create a minimal streaming DataFrame for testing
    # Write sample data to a temp directory
    data_dir = tmp_path / "streaming_test"
    data_dir.mkdir()

    sample_df = spark_session.createDataFrame(
        [(1, 101, 1609459200.0, 25.0, "°C", "sensors/temperature", "corr-1")],
        ["plant_id", "sensor_id", "timestamp", "value", "unit", "topic", "correlation_id"],
    )
    sample_df.write.parquet(str(data_dir / "data.parquet"))

    # Create streaming DataFrame
    raw_events = spark_session.readStream.schema(sample_df.schema).parquet(str(data_dir))

    result = adapter.setup_watermark(raw_events, "45 minutes")

    # Verify the result is a streaming DataFrame with watermark
    assert result.isStreaming
    # Check that event_time column was added
    assert "event_time" in result.columns
    # Verify the original columns are still present
    assert "timestamp" in result.columns
    assert "plant_id" in result.columns


def test_setup_watermark_requires_streaming_input(spark_adapter) -> None:
    """Test that setup_watermark requires a streaming DataFrame."""
    raw_events = Mock()
    raw_events.isStreaming = False

    with pytest.raises(ValueError, match="requires a streaming DataFrame"):
        spark_adapter.setup_watermark(raw_events, "30 minutes")


def test_build_preprocessing_stream_requires_streaming_input(spark_adapter) -> None:
    """Test that build_preprocessing_stream requires a streaming DataFrame."""
    spark = Mock()
    raw_events = Mock()
    raw_events.isStreaming = False

    with pytest.raises(ValueError, match="requires a streaming DataFrame"):
        spark_adapter.build_preprocessing_stream(spark, raw_events)


def test_build_preprocessing_stream_configures_stateful_processing(spark_adapter):
    """Test that build_preprocessing_stream sets up Spark stateful processing correctly."""
    spark = Mock()

    watermarked = Mock()
    spark_adapter.setup_watermark = Mock(return_value=watermarked)

    raw_events = Mock()
    raw_events.isStreaming = True

    broadcast = Mock()
    spark.sparkContext.broadcast.return_value = broadcast

    grouped = Mock()
    watermarked.groupBy.return_value = grouped

    result_df = Mock()
    grouped.applyInPandasWithState.return_value = result_df

    result = spark_adapter.build_preprocessing_stream(spark, raw_events)

    spark.sparkContext.broadcast.assert_called_once_with(spark_adapter._config_manager)
    spark_adapter.setup_watermark.assert_called_once_with(raw_events, "30 minutes")
    watermarked.groupBy.assert_called_once_with("plant_id", "sensor_id")

    args, kwargs = grouped.applyInPandasWithState.call_args
    assert callable(args[0])
    assert kwargs["outputStructType"] == ProcessedSensorData.get_spark_schema()
    assert kwargs["stateStructType"] == SensorState.get_spark_schema()
    assert kwargs["outputMode"] == "update"
    assert kwargs["timeoutConf"] == GroupStateTimeout.EventTimeTimeout

    assert result is result_df


def test_process_sensor_group_stateful_emits_processed_frame(
    spark_adapter, config_manager, monkeypatch
):
    """Test that _process_sensor_group_stateful processes readings correctly."""
    # Monkeypatch to use real SparkStateProvider but with mocked GroupState

    class TestableStateProvider(SparkStateProvider):
        """StateProvider that tracks calls for testing."""

        instances: list["TestableStateProvider"] = []

        def __init__(self, group_state, sensor_id, max_history_length=100):
            super().__init__(group_state, sensor_id, max_history_length)
            TestableStateProvider.instances.append(self)

    TestableStateProvider.instances.clear()
    monkeypatch.setattr(
        "dt.data.preprocess.spark_adapter.SparkStateProvider",
        TestableStateProvider,
    )

    # Add sensor to registry so it resolves correctly
    config_manager._db_client = Mock()
    config_manager.sensor_registry = {42: "dht22.temperature"}

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    timestamp_values = [
        (base_time.timestamp() + 100),  # First reading
        (base_time.timestamp()),  # Second reading (earlier)
    ]

    data = _make_dataframe(
        [
            {
                "plant_id": 1,
                "sensor_id": 42,
                "timestamp": timestamp_values[0],
                "value": 25.0,
                "unit": "°C",
                "topic": Topics.TEMPERATURE.value,
                "correlation_id": "corr-1",
            },
            {
                "plant_id": 1,
                "sensor_id": 42,
                "timestamp": timestamp_values[1],
                "value": 20.0,
                "unit": "°C",
                "topic": Topics.TEMPERATURE.value,
                "correlation_id": "corr-2",
            },
        ]
    )

    group_state = _make_group_state(has_timed_out=False, watermark_ms=1_500_000)

    key = (1, 42)
    iterator: Iterator[pd.DataFrame] = iter([data])
    result_iter = spark_adapter._process_sensor_group_stateful(
        key,
        iterator,
        group_state,
        config_manager,
    )

    result_list = list(result_iter)
    assert len(result_list) == 1
    output_pdf = result_list[0]
    assert list(output_pdf.columns) == list(PROCESSED_EVENT_COLUMNS)
    assert len(output_pdf) == 2

    # Check that readings were sorted by timestamp
    assert list(output_pdf["timestamp"]) == sorted(timestamp_values)

    # Verify state provider was instantiated
    assert TestableStateProvider.instances, "State provider should be instantiated"
    state_provider = TestableStateProvider.instances[-1]

    # Verify state was updated with valid readings
    # Both readings should be valid (within range)
    assert state_provider._state.last_valid is not None

    # Verify timeout was set
    group_state.setTimeoutTimestamp.assert_called_once()


def test_process_sensor_group_handles_state_timeout(spark_adapter):
    """Test that state timeouts are handled correctly."""
    group_state = _make_group_state(has_timed_out=True)
    key = (1, 99)
    iterator: Iterator[pd.DataFrame] = iter([])

    result_iter = spark_adapter._process_sensor_group_stateful(
        key,
        iterator,
        group_state,
        spark_adapter._config_manager,
    )

    assert list(result_iter) == []
    group_state.remove.assert_called_once_with()


def test_process_readings_with_valid_sensor(spark_adapter, config_manager):
    """Test _process_readings with valid sensor data."""
    # Add sensor to registry
    config_manager.sensor_registry = {101: "dht22.temperature"}

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)

    reading = RawSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=base_time.timestamp(),
        value=25.0,
        unit="°C",
        topic=Topics.TEMPERATURE,
        correlation_id="test-1",
    )

    # Create real SparkStateProvider with mocked GroupState
    group_state = _make_group_state()
    state_provider = SparkStateProvider(
        group_state=group_state,
        sensor_id=101,
        max_history_length=100,
    )

    records, latest_timestamp = spark_adapter._process_readings(
        readings=[reading],
        state_provider=state_provider,
        watermark_seconds=None,
        config_manager=config_manager,
    )

    assert len(records) == 1
    record = records[0]
    assert record["sensor_id"] == reading.sensor_id
    # Value should be calibrated: 25.0 * 1.05 - 0.5 = 25.75
    assert record["value"] == 25.75
    assert record["raw_value"] == 25.0
    assert record["calibrated_value"] == 25.75
    assert record["flags"][ValidationFlag.VALID] is True
    assert record["dq_score"] == 1.0
    assert latest_timestamp == reading.timestamp


def test_process_readings_emits_invalid_record_on_drop(spark_adapter, config_manager):
    """Test that dropped readings emit invalid records."""
    # Add sensor to registry
    config_manager.sensor_registry = {101: "dht22.temperature"}

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)

    # Out of range reading (range is -40 to 80 for dht22.temperature)
    reading = RawSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=base_time.timestamp(),
        value=200.0,  # Out of range
        unit="°C",
        topic=Topics.TEMPERATURE,
        correlation_id="drop-1",
    )

    # Create real SparkStateProvider with mocked GroupState
    group_state = _make_group_state()
    state_provider = SparkStateProvider(
        group_state=group_state,
        sensor_id=101,
        max_history_length=100,
    )

    records, latest_timestamp = spark_adapter._process_readings(
        readings=[reading],
        state_provider=state_provider,
        watermark_seconds=None,
        config_manager=config_manager,
    )

    assert len(records) == 1
    record = records[0]
    assert record["sensor_id"] == reading.sensor_id
    assert record["dq_score"] == 0.0  # Invalid record
    assert record["flags"][ValidationFlag.VALID] is False
    assert record["flags"][ValidationFlag.RANGE] is True
    assert latest_timestamp == reading.timestamp


def test_process_readings_handles_unknown_sensor(spark_adapter, config_manager):
    """Test that unknown sensors are skipped gracefully."""
    # Don't add sensor to registry
    config_manager.sensor_registry = {}

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)

    reading = RawSensorData(
        plant_id=1,
        sensor_id=999,  # Unknown
        timestamp=base_time.timestamp(),
        value=25.0,
        unit="°C",
        topic=Topics.TEMPERATURE,
        correlation_id="unknown",
    )

    group_state = _make_group_state()
    state_provider = SparkStateProvider(
        group_state=group_state,
        sensor_id=999,
        max_history_length=100,
    )

    records, latest_timestamp = spark_adapter._process_readings(
        readings=[reading],
        state_provider=state_provider,
        watermark_seconds=None,
        config_manager=config_manager,
    )

    # Unknown sensor should be skipped
    assert len(records) == 0
    assert latest_timestamp is None
