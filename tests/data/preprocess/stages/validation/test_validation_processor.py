from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from dt.data.preprocess.config.types import RangeConfig, RocConfig, SensorConfig, StuckConfig, ValidationConfig
from dt.data.preprocess.stages.validation.scoring import compute_dq_score
from dt.data.preprocess.core.context import ProcessingContext
from dt.data.preprocess.stages.validation import ValidationProcessor
from dt.data.preprocess.core.state import StateProvider
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.topics import Topics


@pytest.fixture
def sensor_config():
    """Create a sample sensor configuration."""
    return SensorConfig(
        units="°C",
        validation=ValidationConfig(
            range=RangeConfig(min=-40, max=80),
            roc=RocConfig(max_per_minute=5.0, profiles={}, active_profile=None),
            stuck=StuckConfig(max_flat_seconds=300),
        ),
        calibration=None,
        normalization=None,
        imputation=None,
        smoothing=None,
    )


@pytest.fixture
def mock_state_provider():
    """Create a mock state provider."""
    provider = Mock(spec=StateProvider)
    provider.get_last_valid.return_value = None
    provider.get_recent_history.return_value = []
    return provider


@pytest.fixture
def mock_config_manager():
    """Create a mock configuration manager."""
    manager = Mock()
    manager.get_dq_weights.return_value = {
        "range_ok": 0.4,
        "roc_ok": 0.3,
        "stuck_ok": 0.3,
    }
    return manager


def test_validation_processor_valid_reading(
    sample_reading, sensor_config, mock_state_provider, mock_config_manager
):
    """Test validation of a valid reading."""
    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
        sensor_config=sensor_config,
        calibrated_reading=sample_reading,
        sensor_key="dht22.temperature",
    )
    processor = ValidationProcessor(mock_config_manager)
    result = processor.process(context)

    assert result.is_valid is True
    # Flags use True = violation, so all should be False (no violations)
    assert result.flags[ValidationFlag.RANGE] is False
    assert result.flags[ValidationFlag.RATE_OF_CHANGE] is False
    assert result.flags[ValidationFlag.STUCK] is False
    assert result.flags[ValidationFlag.VALID] is True
    assert result.dq_score == 1.0


def test_validation_processor_requires_validation_config(sample_reading, mock_state_provider, mock_config_manager):
    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
        sensor_config=SensorConfig(
            units="°C",
            validation=None,
            calibration=None,
            normalization=None,
            imputation=None,
            smoothing=None,
        ),
        calibrated_reading=sample_reading,
        sensor_key="dht22.temperature",
    )

    processor = ValidationProcessor(mock_config_manager)
    with pytest.raises(ValueError, match="validation"):
        processor.process(context)


def test_validation_processor_out_of_range(sensor_config, mock_state_provider, mock_config_manager):
    """Test validation fails for out-of-range value."""
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    out_of_range_reading = RawSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=base_time.timestamp(),
        value=100.0,  # Out of range
        unit="°C",
        topic=Topics.TEMPERATURE,
        correlation_id="test-correlation-id",
    )

    context = ProcessingContext(
        reading=out_of_range_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
        sensor_config=sensor_config,
    )
    context.calibrated_reading = out_of_range_reading
    context.sensor_key = "dht22.temperature"

    processor = ValidationProcessor(mock_config_manager)
    context = processor.process(context)

    assert context.is_valid is False
    # Flags use True = violation
    assert context.flags[ValidationFlag.RANGE] is True  # Range violation occurred
    assert context.flags[ValidationFlag.VALID] is False
    flags = {
        ValidationFlag.RANGE: True,
        ValidationFlag.RATE_OF_CHANGE: False,
        ValidationFlag.STUCK: False,
        ValidationFlag.VALID: False,
    }
    assert context.flags == flags
    assert context.dq_score == compute_dq_score(flags, mock_config_manager.get_dq_weights())
    assert context.dq_score < 1.0


def test_validation_processor_rate_of_change_violation(
    sensor_config, mock_state_provider, mock_config_manager
):
    """Test validation fails for rate-of-change violation."""
    # Mock previous valid reading
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    previous_reading = RawSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=base_time.timestamp() - 10,  # 10 seconds earlier
        value=20.0,
        unit="°C",
        topic=Topics.TEMPERATURE,
        correlation_id="previous",
    )
    mock_state_provider.get_last_valid.return_value = previous_reading

    # Current reading has jumped 10 degrees in 10 seconds = 60 deg/min (exceeds 5 deg/min limit)
    current_reading = RawSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=base_time.timestamp(),
        value=30.0,
        unit="°C",
        topic=Topics.TEMPERATURE,
        correlation_id="current",
    )

    context = ProcessingContext(
        reading=current_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
        sensor_config=sensor_config,
    )
    context.calibrated_reading = current_reading
    context.sensor_key = "dht22.temperature"

    processor = ValidationProcessor(mock_config_manager)
    result = processor.process(context)

    assert result.is_valid is False
    # Flags use True = violation
    assert result.flags[ValidationFlag.RATE_OF_CHANGE] is True  # ROC violation occurred
    assert result.flags[ValidationFlag.VALID] is False
    assert result.dq_score < 1.0


def test_validation_processor_stuck_sensor(
    sample_reading, sensor_config, mock_state_provider, mock_config_manager
):
    """Test validation fails for stuck sensor."""
    # Mock history with flatlined values over 400 seconds
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    history = [
        RawSensorData(
            plant_id=1,
            sensor_id=101,
            timestamp=base_time.timestamp() - i * 100,  # 0, 100, 200, 300, 400 seconds ago
            value=25.5,
            unit="°C",
            topic=Topics.TEMPERATURE,
            correlation_id=f"hist-{i}",
        )
        for i in range(5)
    ]
    mock_state_provider.get_recent_history.return_value = history

    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
        sensor_config=sensor_config,
    )
    context.calibrated_reading = sample_reading
    context.sensor_key = "dht22.temperature"

    processor = ValidationProcessor(mock_config_manager)
    result = processor.process(context)

    assert result.is_valid is False
    # Flags use True = violation
    assert result.flags[ValidationFlag.STUCK] is True  # Stuck violation occurred
    assert result.flags[ValidationFlag.VALID] is False
    assert result.dq_score < 1.0
    # Verify flatline was recorded
    mock_state_provider.record_flatline.assert_called_once_with(
        sensor_id=101, value=25.5, timestamp=sample_reading.timestamp
    )


def test_validation_processor_calculates_dq_score(
    sensor_config, mock_state_provider, mock_config_manager
):
    """Test data quality score calculation with weighted flags."""
    # Fail only range check
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    out_of_range_reading = RawSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=base_time.timestamp(),
        value=100.0,
        unit="°C",
        topic=Topics.TEMPERATURE,
        correlation_id="test",
    )

    context = ProcessingContext(
        reading=out_of_range_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
        sensor_config=sensor_config,
    )
    context.calibrated_reading = out_of_range_reading
    context.sensor_key = "dht22.temperature"

    processor = ValidationProcessor(mock_config_manager)
    result = processor.process(context)

    # range=0, roc=1, stuck=1
    # DQ = 0.4*0 + 0.3*1 + 0.3*1 = 0.6
    assert result.dq_score == 0.6


def test_validation_processor_detects_late_event_by_watermark(
    sample_reading, sensor_config, mock_state_provider, mock_config_manager
):
    """Test late event detection based on watermark."""
    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=9999999999.0,  # Far future
        sensor_config=sensor_config,
    )
    context.calibrated_reading = sample_reading
    context.sensor_key = "dht22.temperature"

    processor = ValidationProcessor(mock_config_manager)
    result = processor.process(context)

    assert result.is_late_event is True


def test_validation_processor_detects_late_event_by_previous_valid(
    sample_reading, sensor_config, mock_state_provider, mock_config_manager
):
    """Test late event detection based on previous valid timestamp."""
    # Mock previous valid reading with future timestamp
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    future_reading = RawSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=base_time.timestamp() + 10,  # Future timestamp
        value=25.0,
        unit="°C",
        topic=Topics.TEMPERATURE,
        correlation_id="future",
    )
    mock_state_provider.get_last_valid.return_value = future_reading

    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
        sensor_config=sensor_config,
    )
    context.calibrated_reading = sample_reading
    context.sensor_key = "dht22.temperature"

    processor = ValidationProcessor(mock_config_manager)
    result = processor.process(context)

    assert result.is_late_event is True
