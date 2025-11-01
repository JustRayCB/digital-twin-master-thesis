from typing import cast

from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.data.preprocess.configuration.preprocessing_config import \
    LinearExtrapolationImputationConfig
from dt.data.preprocess.imputers.base import ImputationStrategy
from dt.data.preprocess.state import StateProvider


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

    def compute(self, sensor_id: int, reading: RawSensorData, state: StateProvider) -> float | None:
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
