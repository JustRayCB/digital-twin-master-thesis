from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics
from dt.data.preprocess.pipeline.context import ProcessingContext
from dt.data.preprocess.processors.smoothing import SmoothingProcessor
from dt.data.preprocess.state import StateProvider


@pytest.fixture
def sample_reading():
    """Create a sample raw sensor reading."""
    basetime = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return RawSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=basetime.timestamp(),
        value=25.0,
        unit="°C",
        topic=Topics.TEMPERATURE,
        correlation_id="test-correlation-id",
    )


@pytest.fixture
def mock_sensor_config():
    """Create a mock sensor configuration."""
    return Mock()


@pytest.fixture
def mock_smoothing_strategy():
    """Create a mock smoothing strategy."""
    strategy = Mock()
    strategy.apply.return_value = 24.5
    return strategy


@pytest.fixture
def mock_config_manager(mock_smoothing_strategy):
    """Create a mock configuration manager."""
    manager = Mock()
    manager.get_smoothing_strategy.return_value = mock_smoothing_strategy
    return manager


def test_smoothing_processor_smooths_value(
    sample_reading,
    mock_state_provider,
    mock_sensor_config,
    mock_config_manager,
    mock_smoothing_strategy,
):
    """Test that smoothing is applied to the value."""
    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
        sensor_config=mock_sensor_config,
    )
    context.calibrated_reading = sample_reading
    context.imputed = False
    context.sensor_key = "dht22.temperature"

    processor = SmoothingProcessor(mock_config_manager)
    result = processor.process(context)

    assert result.smoothed_value == 24.5
    mock_smoothing_strategy.apply.assert_called_once()


def test_smoothing_processor_uses_imputed_value(
    sample_reading,
    mock_state_provider,
    mock_sensor_config,
    mock_config_manager,
    mock_smoothing_strategy,
):
    """Test that smoothing uses imputed value when available."""
    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
        sensor_config=mock_sensor_config,
    )
    context.calibrated_reading = sample_reading
    context.imputed = True
    context.imputed_value = 30.0
    context.sensor_key = "dht22.temperature"

    processor = SmoothingProcessor(mock_config_manager)
    result = processor.process(context)

    # Verify smooth was called with imputed_value
    call_args = mock_smoothing_strategy.apply.call_args
    assert call_args[1]["value"] == 30.0


def test_smoothing_processor_uses_calibrated_value_when_not_imputed(
    sample_reading,
    mock_state_provider,
    mock_sensor_config,
    mock_config_manager,
    mock_smoothing_strategy,
):
    """Test that smoothing uses calibrated value when not imputed."""
    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
        sensor_config=mock_sensor_config,
    )
    context.calibrated_reading = sample_reading
    context.imputed = False
    context.sensor_key = "dht22.temperature"

    processor = SmoothingProcessor(mock_config_manager)
    result = processor.process(context)

    # Verify smooth was called with calibrated value
    call_args = mock_smoothing_strategy.apply.call_args
    assert call_args[1]["value"] == 25.0
