from abc import ABC, abstractmethod


class CalibrationStrategy(ABC):
    """Apply calibration logic to raw sensor values."""

    @abstractmethod
    def apply(self, value: float) -> float:
        """Return the calibrated value for ``value``."""
