from unittest.mock import Mock

from dt.data.preprocess.config.types import SensorConfig
from dt.data.preprocess.core.context import ProcessingContext
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.topics import Topics


def test_context_initialization(sample_reading, mock_state_provider):
    """Test that context can be initialized with minimal required fields."""
    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
    )

    assert context.reading == sample_reading
    assert context.state_provider == mock_state_provider
    assert context.watermark_seconds is None
    assert context.calibrated_reading is None
    assert context.flags == {
        ValidationFlag.RANGE: False,
        ValidationFlag.STUCK: False,
        ValidationFlag.RATE_OF_CHANGE: False,
        ValidationFlag.VALID: True,
    }
    assert context.imputed_value is None
    assert context.smoothed_value is None
    assert context.normalized_value is None


def test_context_with_sensor_identifiers(sample_reading, mock_state_provider):
    """Test context tracks sensor key and config."""
    mock_sensor_config = Mock(SensorConfig)
    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
        sensor_key="dht22.temperature",
        sensor_config=mock_sensor_config,
    )

    assert context.sensor_key == "dht22.temperature"
    assert context.sensor_config is not None


def test_context_mutability(sample_reading, mock_state_provider):
    """Test that context fields can be updated during processing."""
    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
    )

    # Simulate calibration step
    calibrated = RawSensorData(
        plant_id=sample_reading.plant_id,
        sensor_id=sample_reading.sensor_id,
        timestamp=sample_reading.timestamp,
        value=26.0,  # Calibrated value
        unit=sample_reading.unit,
        topic=sample_reading.topic,
        correlation_id=sample_reading.correlation_id,
    )
    context.calibrated_reading = calibrated
    context.calibration_profile_id = "affine.dht22"

    assert context.calibrated_reading.value == 26.0
    assert context.calibration_profile_id == "affine.dht22"

    # Simulate validation step
    context.flags = {ValidationFlag.VALID: True}
    context.is_valid = True
    context.dq_score = 1.0

    assert context.is_valid is True
    assert context.dq_score == 1.0
    assert context.flags == {ValidationFlag.VALID: True}


def test_context_to_dict(sample_reading, mock_state_provider):
    """Test context can be converted to processed record dict."""
    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
    )

    # Populate with processed values
    context.calibrated_reading = sample_reading
    context.calibration_profile_id = "test-profile"
    context.normalization_profile_id = "test-norm"
    context.flags = {ValidationFlag.VALID: True}
    context.dq_score = 1.0
    context.imputed = False
    context.smoothed_value = 25.5
    context.normalized_value = 0.5

    record = context.to_dict()

    assert record["plant_id"] == 1
    assert record["sensor_id"] == 101
    assert record["value"] == 25.5
    assert record["calibration_profile_id"] == "test-profile"
    assert record["dq_score"] == 1.0


def test_context_mark_invalid(sample_reading, mock_state_provider):
    """Test that marking a flag as invalid updates context state."""
    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
    )

    context.mark_invalid_flag(ValidationFlag.RANGE)

    assert context.flags[ValidationFlag.RANGE] is True
    assert context.is_valid is False
    assert context.flags[ValidationFlag.VALID] is False


def test_context_has_violations(sample_reading, mock_state_provider):
    """Test has_violations method reflects flag states."""
    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
    )

    assert context.has_violations() is False

    context.mark_invalid_flag(ValidationFlag.STUCK)

    assert context.has_violations() is True


def test_context_get_final_value(sample_reading, mock_state_provider):
    """Test get_final_value method returns correct processed value."""
    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
    )

    # No processing done yet
    assert context.get_final_value() == sample_reading.value

    # After calibration
    calibrated = RawSensorData(
        plant_id=sample_reading.plant_id,
        sensor_id=sample_reading.sensor_id,
        timestamp=sample_reading.timestamp,
        value=27.0,
        unit=sample_reading.unit,
        topic=sample_reading.topic,
        correlation_id=sample_reading.correlation_id,
    )
    context.calibrated_reading = calibrated
    assert context.get_final_value() == 27.0

    # After imputation
    context.imputed_value = 28.0
    assert context.get_final_value() == 28.0

    # After smoothing
    context.smoothed_value = 29.0
    assert context.get_final_value() == 29.0


def test_context_without_optional_fields(sample_reading, mock_state_provider):
    """Test context behavior when optional fields are not set."""
    context = ProcessingContext(
        reading=sample_reading,
        state_provider=mock_state_provider,
        watermark_seconds=None,
    )

    # Ensure optional fields are None
    assert context.calibrated_reading is None
    assert context.calibration_profile_id is ""
    assert context.normalization_profile_id is ""
    assert context.imputed is False
    assert context.imputed_value is None
    assert context.smoothed_value is None
    assert context.normalized_value is None
    assert context.flags == {
        ValidationFlag.RANGE: False,
        ValidationFlag.STUCK: False,
        ValidationFlag.RATE_OF_CHANGE: False,
        ValidationFlag.VALID: True,
    }
    assert context.is_late_event is False
    assert context.is_valid is True
    assert context.dq_score == 1.0

    # Check final value falls back to raw reading
    assert context.get_final_value() == sample_reading.value
    assert context.has_violations() is False
