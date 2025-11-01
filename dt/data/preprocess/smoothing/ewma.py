from dt.data.preprocess.configuration.preprocessing_config import (
    EWMASmoothingConfig, SmoothingConfig)
from dt.data.preprocess.smoothing.base import SmoothingStrategy
from dt.data.preprocess.state import StateProvider


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
