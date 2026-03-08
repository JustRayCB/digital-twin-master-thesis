from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from dt.data.preprocess.config.types import (
    AffineCalibrationConfig,
    CalibrationConfig,
    PiecewiseLookupCalibrationConfig,
    PiecewiseSegment,
)


class CalibrationStrategy(ABC):
    """Apply calibration logic to raw sensor values."""

    @abstractmethod
    def apply(self, value: float) -> float:
        """Return the calibrated value for ``value``."""


class IdentityCalibration(CalibrationStrategy):
    """Return values unchanged."""

    def apply(self, value: float) -> float:
        return float(value)


class AffineCalibration(CalibrationStrategy):
    """Apply an affine transform using ``scale`` and ``offset``."""

    def __init__(self, scale: float = 1.0, offset: float = 0.0) -> None:
        self._scale = float(scale)
        self._offset = float(offset)

    @classmethod
    def from_parameters(cls, parameters: AffineCalibrationConfig) -> AffineCalibration:
        return cls(scale=parameters.scale, offset=parameters.offset)

    def apply(self, value: float) -> float:
        return self._scale * float(value) + self._offset


class PiecewiseLookupCalibration(CalibrationStrategy):
    """Map value ranges to constant outputs."""

    def __init__(self, segments: Iterable[PiecewiseSegment]) -> None:
        self._segments = tuple(segments)
        if not self._segments:
            raise ValueError("piecewise_lookup requires at least one segment")

    @classmethod
    def from_parameters(
        cls, parameters: PiecewiseLookupCalibrationConfig
    ) -> PiecewiseLookupCalibration:
        return cls(parameters.segments)

    def apply(self, value: float) -> float:
        value = float(value)
        for segment in self._segments:
            if segment.input_min <= value < segment.input_max:
                return segment.output
        raise ValueError(f"No lookup segment matches value {value}")


def build_calibration_strategy(params: CalibrationConfig | None) -> CalibrationStrategy:
    """Instantiate the calibration strategy described by ``params``."""
    if params is None or params.strategy == "identity":
        return IdentityCalibration()

    if isinstance(params, AffineCalibrationConfig):
        return AffineCalibration.from_parameters(params)

    if isinstance(params, PiecewiseLookupCalibrationConfig):
        return PiecewiseLookupCalibration.from_parameters(params)

    raise ValueError(f"Unsupported calibration strategy parameters: {params}")