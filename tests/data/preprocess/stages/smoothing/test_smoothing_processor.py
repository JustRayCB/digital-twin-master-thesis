from unittest.mock import Mock

from dt.data.preprocess.config.types import SensorConfig
from dt.data.preprocess.core.context import ProcessingContext
from dt.data.preprocess.config.types import PassThroughSmoothingConfig
from dt.data.preprocess.stages.smoothing import PassThroughSmoothing
from dt.data.preprocess.stages.smoothing import SmoothingProcessor


def test_smoothing_processor_uses_calibrated_value_when_not_imputed(
    sample_reading, mock_state_provider
) -> None:
    """Smoothing uses calibrated value when the reading is not imputed."""
    strategy = PassThroughSmoothing(PassThroughSmoothingConfig())
    config_manager = Mock()
    config_manager.get_smoothing_strategy.return_value = strategy

    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
        sensor_config=SensorConfig(units="C"),
        sensor_key="dht22.temperature",
    )
    context.calibrated_reading = sample_reading
    context.imputed = False

    processor = SmoothingProcessor(config_manager)
    result = processor.process(context)

    assert result.smoothed_value == sample_reading.value


def test_smoothing_processor_uses_imputed_value(
    sample_reading, mock_state_provider
) -> None:
    """Smoothing uses imputed_value when it exists on the context."""
    strategy = PassThroughSmoothing(PassThroughSmoothingConfig())
    config_manager = Mock()
    config_manager.get_smoothing_strategy.return_value = strategy

    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
        sensor_config=SensorConfig(units="C"),
        sensor_key="dht22.temperature",
    )
    context.calibrated_reading = sample_reading
    context.imputed = True
    context.imputed_value = 30.0

    processor = SmoothingProcessor(config_manager)
    result = processor.process(context)

    assert result.smoothed_value == 30.0
