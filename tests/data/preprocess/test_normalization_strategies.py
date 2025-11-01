import pytest

from dt.data.preprocess.configuration.profiles import \
    MinMaxNormalizationParameters
from dt.data.preprocess.normalization import build_normalization_strategy


def test_identity_normalization_returns_same_value(make_profile) -> None:
    profile = make_profile("identity", None)
    strategy = build_normalization_strategy(profile)

    assert strategy.apply(3.2) == 3.2


def test_min_max_normalization_scales_and_clamps(make_profile) -> None:
    profile = make_profile(
        "min_max",
        MinMaxNormalizationParameters(
            input_min=0.0,
            input_max=100.0,
            output_min=0.0,
            output_max=1.0,
            clip=True,
        ),
    )
    strategy = build_normalization_strategy(profile)

    assert strategy.apply(0.0) == 0.0
    assert strategy.apply(50.0) == 0.5
    assert strategy.apply(120.0) == 1.0
    assert strategy.apply(-10.0) == 0.0


def test_min_max_normalization_without_clipping_allows_extrapolation(make_profile) -> None:
    profile = make_profile(
        "min_max",
        MinMaxNormalizationParameters(
            input_min=0.0,
            input_max=10.0,
            output_min=-1.0,
            output_max=1.0,
            clip=False,
        ),
    )
    strategy = build_normalization_strategy(profile)

    assert strategy.apply(15.0) == 2.0
    assert strategy.apply(-5.0) == -2.0


def test_unknown_strategy_raises_error(make_profile) -> None:
    profile = make_profile("unsupported", None)

    with pytest.raises(ValueError):
        build_normalization_strategy(profile)
