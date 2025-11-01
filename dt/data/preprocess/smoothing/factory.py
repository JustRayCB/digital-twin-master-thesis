from dt.data.preprocess.configuration.preprocessing_config import (
    EWMASmoothingConfig, PassThroughSmoothingConfig, SensorConfig)

from .base import SmoothingStrategy
from .ewma import EWMASmoothing
from .pass_through import PassThroughSmoothing


def build_smoothing_strategy(sensor_config: SensorConfig) -> SmoothingStrategy:
    """Instantiate the configured smoothing strategy for a sensor.

    Parameters
    ----------
    sensor_config : SensorConfig
        Sensor definition containing a smoothing configuration section.

    Returns
    -------
    SmoothingStrategy
        Strategy instance matching the configuration, defaulting to
        :class:`PassThroughSmoothing`.

    Raises
    ------
    TypeError
        Raised when the provided configuration does not match the expected
        type for the selected strategy.
    ValueError
        Raised when the requested strategy name is not registered.
    """

    config = sensor_config.smoothing or PassThroughSmoothingConfig()
    strategy_name = config.strategy
    if strategy_name == "pass_through":
        return PassThroughSmoothing(config)
    if strategy_name == "ewma":
        if not isinstance(config, EWMASmoothingConfig):
            raise TypeError("EWMA smoothing requires EWMASmoothingConfig")
        return EWMASmoothing(config)

    raise ValueError(f"Unsupported smoothing strategy '{getattr(config, 'strategy', None)}'")
