from dataclasses import dataclass

import pytest

from dt.data.preprocess.config.types import (
    IdentityNormalizationConfig,
    MinMaxNormalizationConfig,
)
from dt.data.preprocess.stages.normalization import (
    IdentityNormalization,
    MinMaxNormalization,
    build_normalization_strategy,
)

def test_identity_normalization_returns_same_value() -> None:
    strategy = build_normalization_strategy(IdentityNormalizationConfig())

    assert isinstance(strategy, IdentityNormalization)
    assert strategy.apply(3.2) == 3.2


def test_min_max_normalization_scales_and_clamps() -> None:
    strategy = build_normalization_strategy(
        MinMaxNormalizationConfig(
            input_min=0.0,
            input_max=100.0,
            output_min=0.0,
            output_max=1.0,
            clip=True,
        )
    )

    assert isinstance(strategy, MinMaxNormalization)
    assert strategy.apply(0.0) == 0.0
    assert strategy.apply(50.0) == 0.5
    assert strategy.apply(120.0) == 1.0
    assert strategy.apply(-10.0) == 0.0


def test_min_max_normalization_without_clipping_allows_extrapolation() -> None:
    strategy = build_normalization_strategy(
        MinMaxNormalizationConfig(
            input_min=0.0,
            input_max=10.0,
            output_min=-1.0,
            output_max=1.0,
            clip=False,
        )
    )

    assert isinstance(strategy, MinMaxNormalization)
    assert strategy.apply(15.0) == 2.0
    assert strategy.apply(-5.0) == -2.0


def test_unknown_strategy_raises_error() -> None:
    @dataclass
    class UnsupportedNormalizationConfig:
        strategy: str = "unsupported"

    with pytest.raises(ValueError):
        build_normalization_strategy(UnsupportedNormalizationConfig())  # type: ignore[arg-type]
