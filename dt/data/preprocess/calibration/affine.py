from __future__ import annotations

from dt.data.preprocess.configuration.profiles import \
    AffineCalibrationParameters

from .base import CalibrationStrategy


class AffineCalibration(CalibrationStrategy):
    """Apply an affine transform using ``scale`` and ``offset``."""

    def __init__(self, scale: float = 1.0, offset: float = 0.0) -> None:
        self._scale = float(scale)
        self._offset = float(offset)

    @classmethod
    def from_parameters(cls, parameters: AffineCalibrationParameters) -> AffineCalibration:
        return cls(scale=parameters.scale, offset=parameters.offset)

    def apply(self, value: float) -> float:
        return self._scale * float(value) + self._offset
