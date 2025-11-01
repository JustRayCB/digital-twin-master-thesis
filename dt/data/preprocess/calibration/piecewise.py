from __future__ import annotations

from typing import Iterable

from dt.data.preprocess.configuration.profiles import (
    PiecewiseLookupParameters, PiecewiseSegment)

from .base import CalibrationStrategy


class PiecewiseLookupCalibration(CalibrationStrategy):
    """Map value ranges to constant outputs."""

    def __init__(self, segments: Iterable[PiecewiseSegment]) -> None:
        self._segments = tuple(segments)
        if not self._segments:
            raise ValueError("piecewise_lookup requires at least one segment")

    @classmethod
    def from_parameters(cls, parameters: PiecewiseLookupParameters) -> PiecewiseLookupCalibration:
        return cls(parameters.segments)

    def apply(self, value: float) -> float:
        value = float(value)
        for segment in self._segments:
            if segment.input_min <= value < segment.input_max:
                return segment.output
        raise ValueError(f"No lookup segment matches value {value}")
