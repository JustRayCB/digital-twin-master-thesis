from abc import ABC, abstractmethod

from dt.data.preprocess.configuration.preprocessing_config import (
    PassThroughSmoothingConfig, SmoothingConfig)
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
