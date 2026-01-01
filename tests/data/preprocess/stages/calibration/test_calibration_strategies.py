import pytest

from dataclasses import dataclass

from dt.data.preprocess.config.types import (
    AffineCalibrationConfig,
    PiecewiseLookupCalibrationConfig,
    PiecewiseSegment,
)
from dt.data.preprocess.stages.calibration import build_calibration_strategy
from dt.data.preprocess.stages.calibration import (
    AffineCalibration,
    IdentityCalibration,
    PiecewiseLookupCalibration,
)


def test_affine_calibration_scales_and_offsets() -> None:
    params = AffineCalibrationConfig(scale=1.1, offset=-0.5)
    strategy = build_calibration_strategy(params)

    assert strategy.apply(10.0) == 10.5  # (10.0 * 1.1) - 0.5
    assert strategy.apply(-2.0) == -2.7  # (-2.0 * 1.1) - 0.5


def test_affine_calibration_defaults_to_identity_parameters() -> None:
    strategy = build_calibration_strategy(AffineCalibrationConfig())

    assert strategy.apply(7.5) == 7.5  # (7.5 * 1.0) + 0.0


def test_piecewise_lookup_returns_segment_output() -> None:
    strategy = build_calibration_strategy(
        PiecewiseLookupCalibrationConfig(
            segments=(
                PiecewiseSegment(input_min=0.0, input_max=10.0, output=1.0),
                PiecewiseSegment(input_min=10.0, input_max=20.0, output=2.0),
            )
        )
    )

    assert strategy.apply(0.0) == 1.0
    assert strategy.apply(9.99) == 1.0
    assert strategy.apply(10.0) == 2.0
    assert strategy.apply(19.9) == 2.0


def test_piecewise_lookup_raises_when_no_segment_matches() -> None:
    strategy = build_calibration_strategy(
        PiecewiseLookupCalibrationConfig(
            segments=(PiecewiseSegment(input_min=0.0, input_max=1.0, output=0.5),)
        )
    )

    with pytest.raises(ValueError):
        strategy.apply(5.0)


def test_unknown_strategy_raises_error() -> None:
    @dataclass
    class UnsupportedCalibrationConfig:
        strategy: str = "unsupported"

    with pytest.raises(ValueError):
        build_calibration_strategy(UnsupportedCalibrationConfig())  # type: ignore[arg-type]
