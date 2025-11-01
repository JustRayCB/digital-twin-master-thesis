from dt.data.preprocess.configuration.preprocessing_config import (
    ForwardFillImputationConfig, LinearExtrapolationImputationConfig,
    SensorConfig, WindowAverageImputationConfig)

from .base import ImputationStrategy
from .forward_fill import ForwardFillWithDecay
from .linear_extrapolation import LinearExtrapolationImputation
from .window_average import WindowAverageImputation


def build_imputation_strategy(sensor_config: SensorConfig) -> ImputationStrategy:
    """Instantiate the imputation strategy configured for a sensor.

    Parameters
    ----------
    sensor_config : SensorConfig
        Sensor definition containing an imputation configuration block.

    Returns
    -------
    ImputationStrategy
        Strategy instance matching the configuration, defaulting to
        :class:`ForwardFillWithDecay` when no explicit strategy is declared.

    Raises
    ------
    ValueError
        Raised when the configuration refers to an unsupported strategy.
    """

    config = sensor_config.imputation or ForwardFillImputationConfig()
    if isinstance(config, ForwardFillImputationConfig):
        return ForwardFillWithDecay(config)
    if isinstance(config, WindowAverageImputationConfig):
        return WindowAverageImputation(config)
    if isinstance(config, LinearExtrapolationImputationConfig):
        return LinearExtrapolationImputation(config)
    raise ValueError(f"Unsupported imputation configuration '{type(config).__name__}'")
