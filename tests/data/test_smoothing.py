
import pytest

from dt.communication.dataclasses.preprocessing_config import (
    EWMASmoothingConfig, PassThroughSmoothingConfig, SensorConfig)
from dt.data.preprocess.smoothing import (EWMASmoothing, PassThroughSmoothing,
                                          build_smoothing_strategy)
from dt.data.preprocess.state import FlatlineRecord, StateProvider


class _DummyState(StateProvider):
    """Minimal state provider for smoothing unit tests."""

    def __init__(self) -> None:
        self._flatlines: dict[int, FlatlineRecord] = {}

    def get_last_valid(self, sensor_id: int):
        return None

    def update(self, sensor_id: int, reading):
        return None

    def record_flatline(self, sensor_id: int, value: float, timestamp: float) -> None:
        self._flatlines[sensor_id] = FlatlineRecord(value=value, timestamp=timestamp)

    def get_flatline(self, sensor_id: int):
        return self._flatlines.get(sensor_id)

    def get_recent_history(self, sensor_id: int, window_seconds: float, reference_timestamp: float):
        return []


def _sensor_config(smoothing):
    """Build a sensor configuration wrapper with the provided smoothing config.

    Parameters
    ----------
    smoothing : SmoothingConfig or None
        Smoothing configuration to attach to the sensor definition.

    Returns
    -------
    SensorConfig
        Configuration instance referencing the supplied smoothing behaviour.
    """
    return SensorConfig(
        units="C",
        range=None,  # type: ignore[arg-type]
        roc=None,  # type: ignore[arg-type]
        stuck=None,  # type: ignore[arg-type]
        imputation=None,
        smoothing=smoothing,
    )


def test_factory_defaults_to_pass_through_when_missing() -> None:
    """Factory returns pass-through smoothing when config is absent."""
    strategy = build_smoothing_strategy(sensor_config=_sensor_config(smoothing=None))

    assert isinstance(strategy, PassThroughSmoothing)


def test_pass_through_strategy_returns_value() -> None:
    """Pass-through smoothing leaves values unchanged."""
    strategy = build_smoothing_strategy(
        sensor_config=_sensor_config(smoothing=PassThroughSmoothingConfig())
    )
    state = _DummyState()

    result = strategy.apply(sensor_id=42, value=15.0, timestamp=1000.0, state=state)

    assert result == 15.0


def test_factory_selects_ewma_strategy() -> None:
    """Factory selects EWMA smoothing when configured."""
    strategy = build_smoothing_strategy(
        sensor_config=_sensor_config(smoothing=EWMASmoothingConfig(alpha=0.4))
    )

    assert isinstance(strategy, EWMASmoothing)


def test_ewma_smoothing_applies_recursive_average() -> None:
    """EWMA smoothing performs exponential averaging across readings."""
    strategy = EWMASmoothing(EWMASmoothingConfig(alpha=0.5))
    state = _DummyState()

    first = strategy.apply(sensor_id=7, value=10.0, timestamp=1_000.0, state=state)
    second = strategy.apply(sensor_id=7, value=14.0, timestamp=1_060.0, state=state)

    assert first == 10.0
    assert second == 12.0


def test_ewma_rejects_alpha_out_of_bounds() -> None:
    """EWMA configuration rejects alpha values outside the open interval (0, 1]."""
    with pytest.raises(ValueError):
        EWMASmoothing(EWMASmoothingConfig(alpha=0.0))
