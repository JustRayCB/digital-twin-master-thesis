from dataclasses import dataclass, field
from typing import Any

from dt.data.preprocess.configuration.preprocessing_config import SensorConfig
from dt.communication.dataclasses.processed_sensor_data import (
    ProcessedSensorData, ValidationFlag)
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.data.preprocess.state import StateProvider


@dataclass
class ProcessingContext:
    """Mutable context passed through the processing pipeline.

    This context object carries all state needed during sensor data processing,
    from the initial raw reading through calibration, validation, imputation,
    smoothing, and normalization.

    Parameters
    ----------
    reading : RawSensorData
        Original raw sensor reading from Kafka.
    state_provider : StateProvider
        Interface to historical sensor state (for validation, imputation).
    watermark_seconds : float or None
        Event-time watermark in seconds since epoch, used for late event detection.
    sensor_key : str or None
        Configuration key for the sensor (e.g., "dht22.temperature").
    sensor_config : SensorConfig or None
        Resolved sensor configuration from preprocessing config.

    Attributes
    ----------
    calibrated_reading : RawSensorData or None
        Reading after calibration is applied.
    calibration_profile_id : str or None
        Identifier of the calibration profile used.
    flags : dict[ValidationFlag, bool]
        Validation results (range, rate-of-change, stuck).
    is_valid : bool or None
        Overall validation status.
    is_late_event : bool
        Whether the reading arrived after the watermark.
    dq_score : float or None
        Data quality score [0, 1].
    imputed : bool
        Whether imputation was performed.
    imputed_value : float or None
        Value after imputation (before smoothing).
    smoothed_value : float or None
        Value after smoothing is applied.
    normalized_value : float or None
        Value after normalization.
    normalization_profile_id : str or None
        Identifier of the normalization profile used.
    """

    # Required inputs
    reading: RawSensorData
    state_provider: StateProvider
    watermark_seconds: float | None

    # Optional sensor identifiers
    sensor_key: str | None = None
    sensor_config: SensorConfig | None = None  # SensorConfig type (avoid circular import)

    # Processing outputs (populated by processors)
    calibrated_reading: RawSensorData | None = None
    calibration_profile_id: str = ""

    flags: dict[ValidationFlag, bool] = field(
        default_factory=lambda: {
            **{flag: False for flag in ValidationFlag},
            ValidationFlag.VALID: True,
        }
    )

    is_late_event: bool = False
    is_valid: bool = True
    dq_score: float = 1.0

    imputed: bool = False
    imputed_value: float | None = None

    smoothed_value: float | None = None

    normalized_value: float | None = None
    normalization_profile_id: str = ""

    def get_final_value(self) -> float:
        """Get the final processed value after all steps.

        Returns
        -------
        float
            Final sensor value after imputation, smoothing, calibration, etc.
        """
        if self.smoothed_value is not None:
            return self.smoothed_value
        if self.imputed_value is not None:
            return self.imputed_value
        if self.calibrated_reading is not None:
            return float(self.calibrated_reading.value)
        return float(self.reading.value)

    def mark_invalid_flag(self, flag: ValidationFlag) -> None:
        """Mark a specific validation flag as invalid.

        Parameters
        ----------
        flag : ValidationFlag
            The validation flag to mark as invalid.
        """
        self.flags[flag] = True
        self.is_valid = False
        self.flags[ValidationFlag.VALID] = False

    def has_violations(self) -> bool:
        """Check if any validation flags are set.

        Returns
        -------
        bool
            True if any validation flags indicate a violation.
        """
        return any(
            {
                flag
                for flag, violated in self.flags.items()
                if flag != ValidationFlag.VALID and violated
            }
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert context to a processed sensor record dictionary.

        Returns
        -------
        dict[str, Any]
            Dictionary matching ProcessedSensorData schema.
        """
        # Use smoothed_value if available, otherwise calibrated or raw
        final_value = self.get_final_value()
        processed = ProcessedSensorData(
            plant_id=self.reading.plant_id,
            sensor_id=self.reading.sensor_id,
            timestamp=self.reading.timestamp,
            value=final_value,
            unit=self.reading.unit,
            topic=self.reading.topic,
            correlation_id=self.reading.correlation_id,
            flags=self.flags,
            dq_score=self.dq_score or 0.0,
            imputed=self.imputed,
            raw_value=self.reading.value,
            calibrated_value=(self.calibrated_reading.value if self.calibrated_reading else None),
            normalized_value=self.normalized_value,
            calibration_profile_id=self.calibration_profile_id,
            normalization_profile_id=self.normalization_profile_id,
        )
        return processed.to_dict()
