from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics
from dt.data.preprocess.configuration.manager import ConfigurationManager
from dt.data.preprocess.pipeline.context import ProcessingContext
from dt.data.preprocess.processors.imputation import ImputationProcessor
from dt.data.preprocess.state import SparkStateProvider
from dt.utils.exceptions.drop_reading import DropReadingException


@pytest.fixture
def mock_group_state():
    """Create a mock Spark GroupState for SparkStateProvider."""
    group_state = Mock()
    group_state.exists = False
    group_state.get = None
    group_state.update = Mock()
    group_state.getCurrentWatermarkMs.return_value = -1
    return group_state


@pytest.fixture
def real_state_provider(mock_group_state):
    """Create a real SparkStateProvider with mocked GroupState."""
    return SparkStateProvider(
        group_state=mock_group_state,
        sensor_id=101,
        max_history_length=100,
    )


@pytest.fixture
def config_manager(test_config_path):
    """Create a real ConfigurationManager with test config."""
    return ConfigurationManager(test_config_path)


def test_imputation_processor_skips_valid_reading(
    sample_reading, real_state_provider, config_manager
):
    """Test that valid readings are not imputed."""
    sensor_key = "dht22.temperature"
    sensor_config = config_manager.rules.sensors[sensor_key]

    context = ProcessingContext(
        reading=sample_reading,
        state_provider=real_state_provider,
        watermark_seconds=None,
        sensor_config=sensor_config,
        sensor_key=sensor_key,
    )
    context.calibrated_reading = sample_reading
    context.is_valid = True

    processor = ImputationProcessor(config_manager)
    result = processor.process(context)

    assert result.imputed is False
    assert result.imputed_value is None


def test_imputation_processor_imputes_invalid_reading(real_state_provider, config_manager):
    """Test that invalid readings are imputed using forward fill with decay."""
    sensor_key = "dht22.temperature"
    sensor_config = config_manager.rules.sensors[sensor_key]

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)

    # Add a previous valid reading to state
    previous_reading = RawSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=base_time.timestamp(),
        value=20.0,
        unit="°C",
        topic=Topics.TEMPERATURE,
        correlation_id="prev",
    )
    real_state_provider.update(101, previous_reading)

    # Create invalid reading 100 seconds later
    invalid_reading = RawSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=(base_time + timedelta(seconds=100)).timestamp(),
        value=200.0,  # Out of range, will be marked invalid
        unit="°C",
        topic=Topics.TEMPERATURE,
        correlation_id="test",
    )

    context = ProcessingContext(
        reading=invalid_reading,
        state_provider=real_state_provider,
        watermark_seconds=None,
        sensor_config=sensor_config,
        sensor_key=sensor_key,
    )
    context.calibrated_reading = invalid_reading
    context.is_valid = False

    processor = ImputationProcessor(config_manager)
    result = processor.process(context)

    assert result.imputed is True
    assert result.imputed_value is not None
    # With forward fill decay, value should be between baseline (if any) and previous value (20.0)
    # Config has decay_seconds=300, max_gap_seconds=600, baseline=null
    # After 100s, decay factor = exp(-100/300) ≈ 0.717
    # Since baseline is null, it should be close to previous value with some decay
    assert 19.0 < result.imputed_value <= 20.0


def test_imputation_processor_raises_when_imputation_fails(real_state_provider, config_manager):
    """Test that DropReadingException is raised when imputation fails."""
    sensor_key = "dht22.temperature"
    sensor_config = config_manager.rules.sensors[sensor_key]

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)

    # No previous valid reading in state
    # Invalid reading should fail imputation
    invalid_reading = RawSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=base_time.timestamp(),
        value=200.0,  # Out of range
        unit="°C",
        topic=Topics.TEMPERATURE,
        correlation_id="test",
    )

    context = ProcessingContext(
        reading=invalid_reading,
        state_provider=real_state_provider,
        watermark_seconds=None,
        sensor_config=sensor_config,
        sensor_key=sensor_key,
    )
    context.calibrated_reading = invalid_reading
    context.is_valid = False

    processor = ImputationProcessor(config_manager)

    with pytest.raises(DropReadingException):
        processor.process(context)


def test_imputation_processor_handles_gap_beyond_max_gap(real_state_provider, config_manager):
    """Test imputation when gap exceeds max_gap_seconds returns baseline."""
    sensor_key = "dht22.temperature"
    sensor_config = config_manager.rules.sensors[sensor_key]

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)

    # Add a previous valid reading
    previous_reading = RawSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=base_time.timestamp(),
        value=20.0,
        unit="°C",
        topic=Topics.TEMPERATURE,
        correlation_id="prev",
    )
    real_state_provider.update(101, previous_reading)

    # Create invalid reading 700 seconds later (beyond max_gap_seconds=600)
    invalid_reading = RawSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=(base_time + timedelta(seconds=700)).timestamp(),
        value=200.0,
        unit="°C",
        topic=Topics.TEMPERATURE,
        correlation_id="test",
    )

    context = ProcessingContext(
        reading=invalid_reading,
        state_provider=real_state_provider,
        watermark_seconds=None,
        sensor_config=sensor_config,
        sensor_key=sensor_key,
    )
    context.calibrated_reading = invalid_reading
    context.is_valid = False

    processor = ImputationProcessor(config_manager)
    result = processor.process(context)

    # When gap exceeds max_gap_seconds, ForwardFillWithDecay returns baseline
    # Since baseline is null in config, it defaults to last_valid.value (20.0)
    assert result.imputed is True
    assert result.imputed_value == 20.0
