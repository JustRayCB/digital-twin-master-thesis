import numpy as np

from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.data.preprocess.configuration.preprocessing_config import StuckConfig


def _is_flatline(values: list[float], var_threshold: float = 1e-3) -> bool:
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

    if len(history) < 2:  # Need at least two points to determine flatline
        return True, ValidationFlag.VALID

    timestamps = [item.timestamp for item in history]
    span_seconds = max(timestamps) - min(timestamps)
    if span_seconds < rule.max_flat_seconds:  # Not enough time to consider flatline
        return True, ValidationFlag.VALID

    values = [item.value for item in history]
    if _is_flatline(values):
        return False, ValidationFlag.STUCK
    return True, ValidationFlag.VALID
