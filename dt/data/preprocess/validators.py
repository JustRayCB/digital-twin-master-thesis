
import numpy as np

from dt.communication.dataclasses.preprocessing_config import RangeConfig, RocConfig, StuckConfig
from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.dataclasses.raw_sensor_data import RawSensorData


def check_range(reading: RawSensorData, rule: RangeConfig) -> tuple[bool, ValidationFlag]:
    """Validate a reading against configured min/max bounds.

    Parameters
    ----------
    reading: RawSensorData
        Sensor reading to evaluate.
    rule : RangeConfig
        Configuration providing the inclusive lower and upper bounds.

    Returns
    -------
    tuple[bool, ValidationFlag]
        Pair whose boolean indicates whether the value sits within the range,
        accompanied by ValidationFlag.RANGE on failure or
        ValidationFlag.VALID on success.
    """
    if reading.value < rule.min or reading.value > rule.max:
        return False, ValidationFlag.RANGE
    return True, ValidationFlag.VALID


def check_rate_of_change(
    reading: RawSensorData, previous_valid: RawSensorData | None, rule: RocConfig
) -> tuple[bool, ValidationFlag]:
    """Validate rate-of-change using the last accepted reading.

    Parameters
    ----------
    reading : RawSensorData
        Current sensor event under validation.
    previous_valid : RawSensorData or None
        Most recent accepted reading; when None the current reading is treated
        as valid.
    rule : RocConfig
        Rate-of-change rule describing the allowed delta per minute.

    Returns
    -------
    tuple[bool, ValidationFlag]
        Pair reporting whether the delta is acceptable. The accompanying flag is
        ValidationFlag.RATE_OF_CHANGE on violation, otherwise
        ValidationFlag.VALID.
    """
    limit_per_minute = rule.active_max_per_minute
    if limit_per_minute is None or previous_valid is None:
        return True, ValidationFlag.VALID

    current_time = reading.timestamp
    previous_time = previous_valid.timestamp
    delta_seconds = current_time - previous_time
    if delta_seconds <= 0:
        return True, ValidationFlag.VALID

    current_value = reading.value
    previous_value = previous_valid.value
    delta_value = abs(current_value - previous_value)
    allowed_delta = (limit_per_minute / 60.0) * delta_seconds  # convert to per-second

    if delta_value > allowed_delta:
        return False, ValidationFlag.RATE_OF_CHANGE
    return True, ValidationFlag.VALID


def check_stuck(history: list[RawSensorData], rule: StuckConfig) -> tuple[bool, ValidationFlag]:
    """Detect flatlined values beyond the configured duration.

    Parameters
    ----------
    history : list[RawSensorData]
        Chronologically ordered readings representing the current rolling window.
    rule : StuckConfig
        Stuck detection rule specifying maximum allowed flatline duration.

    Returns
    -------
    tuple[bool, ValidationFlag]
        Pair reporting whether the window is considered stuck, together with
        ValidationFlag.STUCK when flatlined beyond the threshold or
        ValidationFlag.VALID otherwise.
    """

    def is_flatline(values: list[float], var_threshold: float = 1e-3) -> bool:
        """Determine whether a sequence is effectively constant.

        Parameters
        ----------
        values : list[float]
            Values sampled within the rolling window.
        var_threshold : float, optional
            Maximum variance tolerated before the sequence is considered non-flat.

        Returns
        -------
        bool
            True when the variance stays below var_threshold, otherwise False.
        """
        if len(values) < 2:
            return False
        variance = np.var(values)
        return bool(variance < var_threshold)

    if len(history) < 2:  # Need at least two points to determine flatline
        return True, ValidationFlag.VALID

    timestamps = [item.timestamp for item in history]
    span_seconds = max(timestamps) - min(timestamps)
    if span_seconds < rule.max_flat_seconds:  # Not enough time to consider flatline
        return True, ValidationFlag.VALID

    values = [item.value for item in history]
    if is_flatline(values):
        return False, ValidationFlag.STUCK
    return True, ValidationFlag.VALID
