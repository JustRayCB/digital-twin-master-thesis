from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from dt.data.preprocess.config.types import MinMaxNormalizationConfig, SensorConfig
from dt.data.preprocess.stages.normalization import IdentityNormalization, MinMaxNormalization
from dt.data.preprocess.core.context import ProcessingContext
from dt.data.preprocess.stages.normalization import NormalizationProcessor


def test_normalization_processor_requires_sensor_config(sample_reading, mock_state_provider) -> None:
    mock_config_manager = Mock()
    mock_config_manager.get_normalization_strategy.return_value = IdentityNormalization()

    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
        sensor_key="dht22.temperature",
        sensor_config=None,
    )
    context.calibrated_reading = sample_reading

    processor = NormalizationProcessor(mock_config_manager)
    with pytest.raises(ValueError, match="sensor_config"):
        processor.process(context)


def test_normalization_processor_requires_sensor_key(sample_reading, mock_state_provider) -> None:
    mock_config_manager = Mock()
    mock_config_manager.get_normalization_strategy.return_value = IdentityNormalization()

    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
        sensor_key=None,
        sensor_config=SensorConfig(units="°C"),
    )
    context.calibrated_reading = sample_reading

    processor = NormalizationProcessor(mock_config_manager)
    with pytest.raises(ValueError, match="sensor_key"):
        processor.process(context)


def test_normalization_processor_applies_identity(sample_reading, mock_state_provider):
    """Test identity normalization passes through the value unchanged."""
    mock_config_manager = Mock()
    mock_config_manager.get_normalization_strategy.return_value = IdentityNormalization()

    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
    )
    context.sensor_config = SensorConfig(
        units="°C",
        validation=None,
        calibration=None,
        normalization=None,
        imputation=None,
        smoothing=None,
        normalization_profile_id="normalization.identity.test",
    )
    context.calibrated_reading = sample_reading
    context.smoothed_value = 25.5
    context.sensor_key = "dht22.temperature"

    processor = NormalizationProcessor(mock_config_manager)
    result = processor.process(context)

    assert result.normalized_value == 25.5
    assert result.normalization_profile_id == "normalization.identity.test"


def test_normalization_processor_applies_minmax(sample_reading, mock_state_provider):
    """Test MinMax normalization."""
    mock_config_manager = Mock()
    mock_config_manager.get_normalization_strategy.return_value = MinMaxNormalization(
        input_min=0.0, input_max=50.0, output_min=0.0, output_max=1.0, clip=False
    )

    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
    )
    context.sensor_config = SensorConfig(
        units="°C",
        validation=None,
        calibration=None,
        normalization=MinMaxNormalizationConfig(
            input_min=0.0,
            input_max=50.0,
            output_min=0.0,
            output_max=1.0,
            clip=False,
        ),
        imputation=None,
        smoothing=None,
        normalization_profile_id="normalization.minmax.dht22",
    )
    context.calibrated_reading = sample_reading
    context.smoothed_value = 25.0
    context.sensor_key = "dht22.temperature"

    processor = NormalizationProcessor(mock_config_manager)
    result = processor.process(context)

    # Expected: (25 - 0) / (50 - 0) = 0.5
    expected_value = (context.smoothed_value - 0.0) / (50.0 - 0.0)
    assert result.normalized_value == expected_value
    assert result.normalization_profile_id == "normalization.minmax.dht22"
