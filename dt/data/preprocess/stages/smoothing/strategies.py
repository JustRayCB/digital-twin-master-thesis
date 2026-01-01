from abc import ABC, abstractmethod
from typing import cast

from dt.data.preprocess.config.types import (
    EWMASmoothingConfig,
    PassThroughSmoothingConfig,
    SmoothingConfig,
)
from dt.data.preprocess.core.state import StateProvider


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


class EWMASmoothing(SmoothingStrategy):
    """Exponentially weighted moving average smoothing strategy."""

    def __init__(self, config: EWMASmoothingConfig) -> None:
        super().__init__(config)
        if not isinstance(self._config, EWMASmoothingConfig):
            raise TypeError("EWMASmoothing requires EWMASmoothingConfig")
        
        self._alpha = float(self.config.alpha)
        if not 0 < self._alpha <= 1:
            raise ValueError("EWMA requires 0 < alpha <= 1")
        self._smoothed: dict[int, float] = {}

    @property
    def config(self) -> EWMASmoothingConfig:
        return cast(EWMASmoothingConfig, super().config)

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


class PassThroughSmoothing(SmoothingStrategy):
    """Smoothing strategy that returns the value unchanged."""

    def __init__(self, config: PassThroughSmoothingConfig) -> None:
        super().__init__(config)

    def apply(self, sensor_id: int, value: float, timestamp: float, state: StateProvider) -> float:
        """Return the original value without applying additional smoothing."""
        return value


def build_smoothing_strategy(params: SmoothingConfig | None) -> SmoothingStrategy:
    """Instantiate the smoothing strategy described by ``params``.

    Parameters
    ----------
    params : SmoothingConfig | None
        The configuration object for smoothing.

    Returns
    -------
    SmoothingStrategy
        The instantiated strategy.

    Raises
    ------
    ValueError
        If the configuration type is not supported.
    """
    if params is None or isinstance(params, PassThroughSmoothingConfig):
        return PassThroughSmoothing(PassThroughSmoothingConfig())

    if isinstance(params, EWMASmoothingConfig):
        return EWMASmoothing(params)

    raise ValueError(f"Unsupported smoothing strategy parameters: {params}")