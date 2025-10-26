import math
from abc import ABC, abstractmethod
from typing import Union, cast

from dt.communication.dataclasses.preprocessing_config import (
    ForwardFillImputationConfig, LinearExtrapolationImputationConfig,
    SensorConfig, WindowAverageImputationConfig)
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
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
    def compute(
        self, sensor_id: int, reading: RawSensorData, state: StateProvider
    ) -> float | None:
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


class ForwardFillWithDecay(ImputationStrategy):
    """Forward-fill strategy that decays toward a baseline as the gap widens."""

    def __init__(self, config: ForwardFillImputationConfig) -> None:
        if not isinstance(config, ForwardFillImputationConfig):
            raise TypeError("ForwardFillWithDecay requires ForwardFillImputationConfig")
        super().__init__(config)

    @property
    def config(self) -> ForwardFillImputationConfig:
        return cast(ForwardFillImputationConfig, super().config)

    def compute(
        self, sensor_id: int, reading: RawSensorData, state: StateProvider
    ) -> float | None:
        """Forward-fill using exponential decay toward a configured baseline.

        Parameters
        ----------
        sensor_id : int
            Sensor identifier used to look up cached state.
        reading : RawSensorData
            Raw reading requiring an imputed replacement.
        state : StateProvider
            Interface exposing prior valid readings for the sensor.

        Returns
        -------
        float or None
            Imputed value respecting decay and max-gap limits, or ``None`` if
            no suitable historical data is available.
        """
        last_valid = state.get_last_valid(sensor_id)
        if last_valid is None:
            return None

        gap_seconds = float(reading.timestamp) - float(last_valid.timestamp)
        if gap_seconds <= 0:
            return float(last_valid.value)

        baseline = (
            float(self.config.baseline)
            if self.config.baseline is not None
            else float(last_valid.value)
        )
        max_gap = max(int(self.config.max_gap_seconds), 0)
        if gap_seconds > max_gap:
            return baseline

        decay_window = max(float(self.config.decay_seconds), 1.0)
        decay = math.exp(-gap_seconds / decay_window)
        last_value = float(last_valid.value)
        return baseline + (last_value - baseline) * decay


class WindowAverageImputation(ImputationStrategy):
    """Impute by averaging recent valid readings within a configurable window."""

    def __init__(self, config: WindowAverageImputationConfig) -> None:
        if not isinstance(config, WindowAverageImputationConfig):
            raise TypeError("WindowAverageImputation requires WindowAverageImputationConfig")
        super().__init__(config)

    @property
    def config(self) -> WindowAverageImputationConfig:
        return cast(WindowAverageImputationConfig, super().config)

    def compute(
        self, sensor_id: int, reading: RawSensorData, state: StateProvider
    ) -> float | None:
        """Compute the mean of recent valid readings inside a sliding window.

        Parameters
        ----------
        sensor_id : int
            Sensor identifier used to retrieve historical readings.
        reading : RawSensorData
            Raw reading scheduled for imputation.
        state : StateProvider
            State interface providing access to the rolling history.

        Returns
        -------
        float or None
            Arithmetic mean of the window when sufficient history exists,
            otherwise ``None``.
        """
        window_seconds = max(float(self.config.window_seconds), 0.0)
        if window_seconds <= 0:
            return None
        min_samples = max(int(self.config.min_samples), 1)
        history = list(
            state.get_recent_history(
                sensor_id=sensor_id,
                window_seconds=window_seconds,
                reference_timestamp=float(reading.timestamp),
            )
        )
        if len(history) < min_samples:
            return None

        values = [float(entry.value) for entry in history if entry.timestamp <= reading.timestamp]
        if len(values) < min_samples:
            return None

        if self.config.max_gap_seconds is not None:
            last_timestamp = float(history[-1].timestamp)
            if float(reading.timestamp) - last_timestamp > float(self.config.max_gap_seconds):
                return None

        return sum(values) / len(values)


class LinearExtrapolationImputation(ImputationStrategy):
    """Impute by extrapolating the recent trend via linear projection."""

    def __init__(self, config: LinearExtrapolationImputationConfig) -> None:
        if not isinstance(config, LinearExtrapolationImputationConfig):
            raise TypeError(
                "LinearExtrapolationImputation requires LinearExtrapolationImputationConfig"
            )
        super().__init__(config)

    @property
    def config(self) -> LinearExtrapolationImputationConfig:
        return cast(LinearExtrapolationImputationConfig, super().config)

    def compute(
        self, sensor_id: int, reading: RawSensorData, state: StateProvider
    ) -> float | None:
        """Extrapolate the recent trend to infer the expected reading value.

        Parameters
        ----------
        sensor_id : int
            Identifier for the sensor stream.
        reading : RawSensorData
            Raw reading that triggered imputation.
        state : StateProvider
            State provider exposing recent valid readings for slope estimation.

        Returns
        -------
        float or None
            Projected value derived from the latest two readings, or ``None``
            when insufficient history exists or gap constraints fail.
        """
        window_seconds = max(float(self.config.window_seconds), 0.0)
        if window_seconds <= 0:
            return None

        history = list(
            state.get_recent_history(
                sensor_id=sensor_id,
                window_seconds=window_seconds,
                reference_timestamp=float(reading.timestamp),
            )
        )
        if len(history) < 2:
            return None

        previous = history[-2]
        last = history[-1]
        delta_time = float(last.timestamp) - float(previous.timestamp)
        if delta_time <= 0:
            return float(last.value)

        gap_seconds = float(reading.timestamp) - float(previous.timestamp)
        if gap_seconds < 0:  # reading is earlier than previous valid reading
            return float(last.value)
        if self.config.max_gap_seconds is not None and gap_seconds > float(
            self.config.max_gap_seconds
        ):
            return None

        slope = (float(last.value) - float(previous.value)) / delta_time
        return float(previous.value) + slope * gap_seconds


def build_strategy(sensor_config: SensorConfig) -> ImputationStrategy:
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
