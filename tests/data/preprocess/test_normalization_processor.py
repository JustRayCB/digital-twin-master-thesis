from datetime import datetime, timezone
from unittest.mock import Mock

from dt.data.preprocess.configuration.profiles import (
    MinMaxNormalizationParameters, ProfileDefinition)
from dt.data.preprocess.normalization import IdentityNormalization, MinMaxNormalization
from dt.data.preprocess.pipeline.context import ProcessingContext
from dt.data.preprocess.processors.normalization import NormalizationProcessor


def test_normalization_processor_applies_identity(sample_reading, mock_state_provider):
    """Test identity normalization passes through the value unchanged."""
    mock_config_manager = Mock()
    mock_config_manager.get_normalization_strategy.return_value = (
        IdentityNormalization(),
        ProfileDefinition(
            profile_id="normalization.identity.test",
            strategy="identity",
            parameters=None,
        ),
    )

    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
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
    mock_config_manager.get_normalization_strategy.return_value = (
        MinMaxNormalization(
            input_min=0.0, input_max=50.0, output_min=0.0, output_max=1.0, clip=False
        ),
        ProfileDefinition(
            profile_id="normalization.minmax.dht22",
            strategy="minmax",
            parameters=MinMaxNormalizationParameters(
                input_min=0.0, input_max=50.0, output_min=0.0, output_max=1.0
            ),
        ),
    )

    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
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
