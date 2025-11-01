from .base import CalibrationStrategy


class IdentityCalibration(CalibrationStrategy):
    """Return values unchanged."""

    def apply(self, value: float) -> float:
        return float(value)
