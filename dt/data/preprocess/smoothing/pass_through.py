from dt.data.preprocess.configuration.preprocessing_config import (
    PassThroughSmoothingConfig, SmoothingConfig)
from dt.data.preprocess.smoothing.base import SmoothingStrategy
from dt.data.preprocess.state import StateProvider


class PassThroughSmoothing(SmoothingStrategy):
    """Smoothing strategy that returns the value unchanged."""

    def __init__(self, config: SmoothingConfig | None = None) -> None:
        super().__init__(config or PassThroughSmoothingConfig())

    def apply(self, sensor_id: int, value: float, timestamp: float, state: StateProvider) -> float:
        """Return the original value without applying additional smoothing."""
        return value
