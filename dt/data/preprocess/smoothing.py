from abc import ABC, abstractmethod

from dt.communication.dataclasses.preprocessing_config import (
    EWMASmoothingConfig, PassThroughSmoothingConfig, SensorConfig,
    SmoothingConfig)
from dt.data.preprocess.state import StateProvider


class SmoothingStrategy(ABC):
    """Base class describing post-imputation smoothing behaviour.

    Parameters
    ----------
    config : SmoothingConfig, optional
        Configuration tuning the smoothing algorithm. Defaults to
        :class:`PassThroughSmoothingConfig`.
    """

    def __init__(self, config: SmoothingConfig | None = None) -> None:
        self._config = config or PassThroughSmoothingConfig()

    @property
    def config(self) -> SmoothingConfig:
        """SmoothingConfig: Configuration driving the smoothing behaviour."""
        return self._config

    @abstractmethod
    def apply(self, sensor_id: int, value: float, timestamp: float, state: StateProvider) -> float:
        """Return a smoothed value for the provided reading.

        Parameters
        ----------
        sensor_id : int
            Sensor identifier used to scope stateful information.
        value : float
            Value produced by the validator and imputation stages.
        timestamp : float
            Event timestamp expressed in seconds.
        state : StateProvider
            State interface for retrieving contextual sensor data.

        Returns
        -------
        float
            Smoothed representation of ``value``.
        """


class PassThroughSmoothing(SmoothingStrategy):
    """Smoothing strategy that returns the value unchanged."""

    def __init__(self, config: SmoothingConfig | None = None) -> None:
        super().__init__(config or PassThroughSmoothingConfig())

    def apply(self, sensor_id: int, value: float, timestamp: float, state: StateProvider) -> float:
        """Return the original value without applying additional smoothing."""
        return value


class EWMASmoothing(SmoothingStrategy):
    """Exponentially weighted moving average smoothing strategy."""

    def __init__(self, config: SmoothingConfig | None = None) -> None:
        if config is None:
            config = EWMASmoothingConfig()
        super().__init__(config)
        if not isinstance(self._config, EWMASmoothingConfig):
            raise TypeError("EWMASmoothing requires EWMASmoothingConfig")
        alpha = self._config.alpha
        if not 0 < alpha <= 1:
            raise ValueError("EWMA requires 0 < alpha <= 1")
        self._alpha = float(alpha)
        self._smoothed: dict[int, float] = {}

    def apply(self, sensor_id: int, value: float, timestamp: float, state: StateProvider) -> float:
        """Apply EWMA smoothing using the configured alpha parameter.

        Parameters
        ----------
        sensor_id : int
            Sensor identifier used to look up prior smoothed values.
        value : float
            Candidate value to smooth.
        timestamp : float
            Event timestamp, unused for EWMA yet preserved for interface symmetry.
        state : StateProvider
            State provider placeholder to match the abstract interface.

        Returns
        -------
        float
            Smoothed value computed via exponential weighting.
        """
        previous = self._smoothed.get(sensor_id)
        if previous is None:
            smoothed = value
        else:
            smoothed = self._alpha * value + (1.0 - self._alpha) * previous
        self._smoothed[sensor_id] = smoothed
        return smoothed


# Registry keeps construction logic declarative.
_SMOOTHING_REGISTRY: dict[str, type[SmoothingStrategy]] = {
    "pass_through": PassThroughSmoothing,
    "ewma": EWMASmoothing,
}


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
    ValueError
        Raised when the requested strategy name is not registered.
    """

    config = sensor_config.smoothing or PassThroughSmoothingConfig()
    try:
        strategy_cls = _SMOOTHING_REGISTRY[config.strategy]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"Unsupported smoothing strategy '{config.strategy}'") from exc
    return strategy_cls(config)
