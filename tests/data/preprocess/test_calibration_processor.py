from unittest.mock import Mock

import pytest

from dt.data.preprocess.configuration.profiles import (
    AffineCalibrationParameters, ProfileDefinition)
from dt.data.preprocess.calibration import AffineCalibration, IdentityCalibration
from dt.data.preprocess.pipeline.context import ProcessingContext
from dt.data.preprocess.processors.calibration import CalibrationProcessor
from dt.data.preprocess.state import StateProvider


def test_calibration_processor_applies_identity(sample_reading, mock_state_provider):
    """Test that identity calibration passes through the value unchanged."""
    mock_config_manager = Mock()
    mock_config_manager.get_calibration_strategy.return_value = (
        IdentityCalibration(),
        ProfileDefinition(
            profile_id="calibration.identity.test",
            strategy="identity",
            parameters=None,
        ),
    )

    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
    )
    context.sensor_key = "dht22.temperature"

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
    mock_config_manager.get_calibration_strategy.return_value = (
        AffineCalibration(scale=scale, offset=offset),
        ProfileDefinition(
            profile_id="calibration.affine.dht22",
            strategy="affine",
            parameters=AffineCalibrationParameters(scale=scale, offset=offset),
        ),
    )

    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
    )
    context.sensor_key = "dht22.temperature"

    processor = CalibrationProcessor(mock_config_manager)
    result = processor.process(context)

    # Expected: 25.5 * 1.1 - 0.5 = 27.0
    assert result.calibrated_reading is not None
    expected_value = sample_reading.value * scale + offset
    assert result.calibrated_reading.value == expected_value
    assert result.calibration_profile_id == "calibration.affine.dht22"


def test_calibration_processor_preserves_metadata(sample_reading, mock_state_provider):
    """Test that calibration preserves all reading metadata."""
    mock_config_manager = Mock()
    mock_config_manager.get_calibration_strategy.return_value = (
        IdentityCalibration(),
        ProfileDefinition(
            profile_id="calibration.identity.test",
            strategy="identity",
            parameters=None,
        ),
    )

    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
    )
    context.sensor_key = "dht22.temperature"

    processor = CalibrationProcessor(mock_config_manager)
    result = processor.process(context)

    assert result.calibrated_reading.plant_id == sample_reading.plant_id
    assert result.calibrated_reading.sensor_id == sample_reading.sensor_id
    assert result.calibrated_reading.timestamp == sample_reading.timestamp
    assert result.calibrated_reading.unit == sample_reading.unit
    assert result.calibrated_reading.topic == sample_reading.topic
    assert result.calibrated_reading.correlation_id == sample_reading.correlation_id
