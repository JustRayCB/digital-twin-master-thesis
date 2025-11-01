import math
from typing import cast

from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.data.preprocess.configuration.preprocessing_config import \
    ForwardFillImputationConfig
from dt.data.preprocess.imputers.base import ImputationStrategy
from dt.data.preprocess.state import StateProvider


class ForwardFillWithDecay(ImputationStrategy):
    """Forward-fill strategy that decays toward a baseline as the gap widens."""

    def __init__(self, config: ForwardFillImputationConfig) -> None:
        if not isinstance(config, ForwardFillImputationConfig):
            raise TypeError("ForwardFillWithDecay requires ForwardFillImputationConfig")
        super().__init__(config)

    @property
    def config(self) -> ForwardFillImputationConfig:
        return cast(ForwardFillImputationConfig, super().config)

    def compute(self, sensor_id: int, reading: RawSensorData, state: StateProvider) -> float | None:
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
