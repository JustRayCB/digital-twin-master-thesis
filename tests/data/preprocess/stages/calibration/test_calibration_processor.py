from unittest.mock import Mock

import pytest

from dt.data.preprocess.config.types import (
    RangeConfig,
    RocConfig,
    SensorConfig,
    StuckConfig,
    ValidationConfig,
)
from dt.data.preprocess.core.context import ProcessingContext
from dt.data.preprocess.core.state import StateProvider
from dt.data.preprocess.stages.calibration import (
    AffineCalibration,
    CalibrationProcessor,
    IdentityCalibration,
)


@pytest.fixture
def sensor_config() -> SensorConfig:
    return SensorConfig(
        units="°C",
        validation=ValidationConfig(
            range=RangeConfig(min=-40, max=80),
            roc=RocConfig(max_per_minute=5.0),
            stuck=StuckConfig(max_flat_seconds=300),
        ),
        calibration=None,
        normalization=None,
        imputation=None,
        smoothing=None,
    )


def test_calibration_processor_requires_sensor_config(sample_reading, mock_state_provider):
    mock_config_manager = Mock()
    mock_config_manager.get_calibration_strategy.return_value = IdentityCalibration()

    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
        sensor_key="dht22.temperature",
        sensor_config=None,
    )

    processor = CalibrationProcessor(mock_config_manager)
    with pytest.raises(ValueError, match="sensor_config"):
        processor.process(context)


def test_calibration_processor_applies_identity(sample_reading, mock_state_provider):
    """Test that identity calibration passes through the value unchanged."""
    mock_config_manager = Mock()
    mock_config_manager.get_calibration_strategy.return_value = IdentityCalibration()

    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
    )
    context.sensor_key = "dht22.temperature"
    context.sensor_config = SensorConfig(
        units="°C",
        validation=None,
        calibration=None,
        normalization=None,
        imputation=None,
        smoothing=None,
        calibration_profile_id="calibration.identity.test",
    )

    processor = CalibrationProcessor(mock_config_manager)
    result = processor.process(context)

    assert result.calibrated_reading is not None
    assert result.calibrated_reading.value == 25.5
    assert result.calibration_profile_id == "calibration.identity.test"
    assert result.calibrated_reading is not sample_reading  # Ensure a new object
    assert result.calibrated_reading.plant_id == sample_reading.plant_id
    assert result.calibrated_reading.sensor_id == sample_reading.sensor_id
    assert result.calibrated_reading.timestamp == sample_reading.timestamp
    assert result.calibrated_reading.unit == sample_reading.unit
    assert result.calibrated_reading.topic == sample_reading.topic
    assert result.calibrated_reading.correlation_id == sample_reading.correlation_id


def test_calibration_processor_applies_affine(sample_reading, mock_state_provider):
    """Test that affine calibration applies scale and offset."""
    scale = 1.1
    offset = -0.5
    mock_config_manager = Mock()
    mock_config_manager.get_calibration_strategy.return_value = AffineCalibration(
        scale=scale, offset=offset
    )

    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
    )
    context.sensor_key = "dht22.temperature"
    context.sensor_config = SensorConfig(
        units="°C",
        validation=None,
        calibration=None,
        normalization=None,
        imputation=None,
        smoothing=None,
        calibration_profile_id="calibration.affine.test",
    )

    processor = CalibrationProcessor(mock_config_manager)
    result = processor.process(context)

    # Expected: 25.5 * 1.1 - 0.5 = 27.0
    assert result.calibrated_reading is not None
    expected_value = sample_reading.value * scale + offset
    assert result.calibrated_reading.value == expected_value
    assert result.calibration_profile_id == "calibration.affine.test"


def test_calibration_processor_preserves_metadata(sample_reading, mock_state_provider):
    """Test that calibration preserves all reading metadata."""
    mock_config_manager = Mock()
    mock_config_manager.get_calibration_strategy.return_value = IdentityCalibration()

    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
    )
    context.sensor_key = "dht22.temperature"
    context.sensor_config = SensorConfig(
        units="°C",
        validation=None,
        calibration=None,
        normalization=None,
        imputation=None,
        smoothing=None,
    )

    processor = CalibrationProcessor(mock_config_manager)
    result = processor.process(context)

    assert result.calibrated_reading.plant_id == sample_reading.plant_id
    assert result.calibrated_reading.sensor_id == sample_reading.sensor_id
    assert result.calibrated_reading.timestamp == sample_reading.timestamp
    assert result.calibrated_reading.unit == sample_reading.unit
    assert result.calibrated_reading.topic == sample_reading.topic
    assert result.calibrated_reading.correlation_id == sample_reading.correlation_id
