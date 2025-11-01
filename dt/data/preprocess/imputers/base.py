from abc import ABC, abstractmethod
from typing import Union

from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.data.preprocess.configuration.preprocessing_config import (
    ForwardFillImputationConfig, LinearExtrapolationImputationConfig,
    WindowAverageImputationConfig)
from dt.data.preprocess.state import StateProvider

ImputationConfig = Union[
    ForwardFillImputationConfig,
    WindowAverageImputationConfig,
    LinearExtrapolationImputationConfig,
]


class ImputationStrategy(ABC):
    """Base class describing the contract for sensor reading imputation.

    Parameters
    ----------
    config : ImputationConfig
        Configuration object governing how the strategy behaves.

    Attributes
    ----------
    _config : ImputationConfig
        Stored configuration used by concrete strategies.
    """

    def __init__(self, config: ImputationConfig) -> None:
        self._config = config

    @property
    def config(self) -> ImputationConfig:
        """ImputationConfig: Configuration backing the strategy instance."""
        return self._config

    @abstractmethod
    def compute(self, sensor_id: int, reading: RawSensorData, state: StateProvider) -> float | None:
        """Return an imputed value for the provided reading.

        Parameters
        ----------
        sensor_id : int
            Identifier for the sensor that produced the reading.
        reading : RawSensorData
            Current raw reading requiring validation or imputation.
        state : StateProvider
            Access point for historical sensor state maintained by the pipeline.

        Returns
        -------
        float or None
            Imputed value to substitute for the reading, or ``None`` when the
            strategy elects not to impute.
        """
