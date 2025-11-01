from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.data.preprocess.configuration.preprocessing_config import RangeConfig


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
