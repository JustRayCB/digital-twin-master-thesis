from typing import cast

from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.data.preprocess.configuration.preprocessing_config import \
    WindowAverageImputationConfig
from dt.data.preprocess.imputers.base import ImputationStrategy
from dt.data.preprocess.state import StateProvider


class WindowAverageImputation(ImputationStrategy):
    """Impute by averaging recent valid readings within a configurable window."""

    def __init__(self, config: WindowAverageImputationConfig) -> None:
        if not isinstance(config, WindowAverageImputationConfig):
            raise TypeError("WindowAverageImputation requires WindowAverageImputationConfig")
        super().__init__(config)

    @property
    def config(self) -> WindowAverageImputationConfig:
        return cast(WindowAverageImputationConfig, super().config)

    def compute(self, sensor_id: int, reading: RawSensorData, state: StateProvider) -> float | None:
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
