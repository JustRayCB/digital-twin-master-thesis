from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.data.preprocess.configuration.preprocessing_config import RocConfig


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
