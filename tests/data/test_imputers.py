import math
from datetime import datetime, timezone

import pytest

from dt.communication.dataclasses.preprocessing_config import (
    ForwardFillImputationConfig, LinearExtrapolationImputationConfig,
    SensorConfig, WindowAverageImputationConfig)
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics
from dt.data.preprocess.imputers import (ForwardFillWithDecay,
                                         LinearExtrapolationImputation,
                                         WindowAverageImputation,
                                         build_imputation_strategy)
from dt.data.preprocess.state import FlatlineRecord, StateProvider


class _InMemoryState(StateProvider):
    """Minimal state provider used to drive imputation unit tests."""

    def __init__(self) -> None:
        self._last_valid: dict[int, RawSensorData] = {}
        self._flatlines: dict[int, FlatlineRecord] = {}
        self._history: dict[int, list[RawSensorData]] = {}

    def get_last_valid(self, sensor_id: int) -> RawSensorData | None:
        return self._last_valid.get(sensor_id)

    def update(self, sensor_id: int, reading: RawSensorData) -> None:
        self._last_valid[sensor_id] = reading
        history = self._history.setdefault(sensor_id, [])
        history.append(reading)
        cutoff = reading.timestamp - 1_000_000  # hard limit to avoid unbounded growth
        self._history[sensor_id] = [row for row in history if row.timestamp >= cutoff]

    def record_flatline(self, sensor_id: int, value: float, timestamp: float) -> None:
        self._flatlines[sensor_id] = FlatlineRecord(value=value, timestamp=timestamp)

    def get_flatline(self, sensor_id: int) -> FlatlineRecord | None:
        return self._flatlines.get(sensor_id)

    def get_recent_history(
        self, sensor_id: int, window_seconds: float, reference_timestamp: float
    ) -> list[RawSensorData]:
        history = self._history.get(sensor_id, [])
        cutoff = reference_timestamp - window_seconds
        trimmed = [row for row in history if row.timestamp >= cutoff]
        self._history[sensor_id] = trimmed
        return trimmed


class _UnknownImputationConfig:
    """Placeholder config used to assert strategy factory validation."""

    pass


def _make_reading(sensor_id: int, value: float, timestamp: float) -> RawSensorData:
    """Build a mock raw sensor reading for imputation tests.

    Parameters
    ----------
    sensor_id : int
        Sensor identifier.
    value : float
        Measured value.
    timestamp : float
        Event timestamp expressed in seconds.

    Returns
    -------
    RawSensorData
        Dataclass instance representing the synthetic reading.
    """
    return RawSensorData(
        plant_id=1,
        sensor_id=sensor_id,
        timestamp=timestamp,
        value=value,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id=f"reading-{sensor_id}",
    )


def _short_config() -> ForwardFillImputationConfig:
    """Return a convenience configuration for forward-fill tests."""
    return ForwardFillImputationConfig(
        max_gap_seconds=180,
        decay_seconds=60,
        baseline=18.0,
    )


def test_forward_fill_with_decay_returns_none_without_history() -> None:
    """Forward-fill strategy returns ``None`` when no historical state exists."""
    provider = _InMemoryState()
    strategy = ForwardFillWithDecay(config=_short_config())
    reading = _make_reading(
        sensor_id=21,
        value=20.0,
        timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp(),
    )

    result = strategy.compute(sensor_id=reading.sensor_id, reading=reading, state=provider)

    assert result is None


def test_forward_fill_with_decay_respects_max_gap() -> None:
    """Forward-fill strategy falls back to baseline after exceeding max gap."""
    provider = _InMemoryState()
    strategy = ForwardFillWithDecay(config=_short_config())
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
    last_valid = _make_reading(sensor_id=42, value=22.0, timestamp=base_time)
    provider.update(sensor_id=last_valid.sensor_id, reading=last_valid)
    reading = _make_reading(
        sensor_id=42,
        value=5.0,
        timestamp=base_time + 600,  # much larger than max_gap_seconds
    )

    result = strategy.compute(sensor_id=reading.sensor_id, reading=reading, state=provider)

    assert result == 18.0


def test_forward_fill_with_decay_applies_exponential_decay() -> None:
    """Forward-fill strategy decays toward baseline proportionally to gap size."""
    provider = _InMemoryState()
    strategy = ForwardFillWithDecay(config=_short_config())
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
    last_valid = _make_reading(sensor_id=7, value=22.0, timestamp=base_time)
    provider.update(sensor_id=last_valid.sensor_id, reading=last_valid)
    reading = _make_reading(
        sensor_id=7,
        value=5.0,
        timestamp=base_time + 30,
    )

    result = strategy.compute(sensor_id=reading.sensor_id, reading=reading, state=provider)

    expected_decay = math.exp(-30 / 60)
    expected_value = 18.0 + (22.0 - 18.0) * expected_decay
    assert result is not None
    assert result == expected_value


def test_forward_fill_with_decay_defaults_baseline_to_last_valid_when_missing() -> None:
    """Forward-fill strategy uses the last valid value when baseline is absent."""
    provider = _InMemoryState()
    config = ForwardFillImputationConfig(
        max_gap_seconds=120,
        decay_seconds=60,
        baseline=None,
    )
    strategy = ForwardFillWithDecay(config=config)
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
    last_valid = _make_reading(sensor_id=9, value=19.0, timestamp=base_time)
    provider.update(sensor_id=last_valid.sensor_id, reading=last_valid)
    reading = _make_reading(
        sensor_id=9,
        value=5.0,
        timestamp=base_time + 45,
    )

    result = strategy.compute(sensor_id=reading.sensor_id, reading=reading, state=provider)

    assert result is not None
    assert result == last_valid.value


def test_build_strategy_rejects_unknown_strategy_name() -> None:
    """Factory rejects imputation configurations with unsupported strategies."""
    sensor_config = SensorConfig(
        units="C",
        range=None,  # type: ignore[arg-type]
        roc=None,  # type: ignore[arg-type]
        stuck=None,  # type: ignore[arg-type]
        imputation=_UnknownImputationConfig(),  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError):
        build_imputation_strategy(sensor_config=sensor_config)


def test_build_strategy_uses_default_when_missing_config() -> None:
    """Factory falls back to forward-fill when imputation config is missing."""
    sensor_config = SensorConfig(
        units="C",
        range=None,  # type: ignore[arg-type]
        roc=None,  # type: ignore[arg-type]
        stuck=None,  # type: ignore[arg-type]
        imputation=None,
    )

    strategy = build_imputation_strategy(sensor_config=sensor_config)
    assert isinstance(strategy, ForwardFillWithDecay)


def test_build_strategy_selects_window_average_strategy() -> None:
    """Factory returns window-average strategy when configured."""
    sensor_config = SensorConfig(
        units="C",
        range=None,  # type: ignore[arg-type]
        roc=None,  # type: ignore[arg-type]
        stuck=None,  # type: ignore[arg-type]
        imputation=WindowAverageImputationConfig(
            window_seconds=30,
            min_samples=2,
            max_gap_seconds=120,
        ),
    )

    strategy = build_imputation_strategy(sensor_config=sensor_config)

    assert isinstance(strategy, WindowAverageImputation)


def test_window_average_strategy_returns_none_when_history_sparse() -> None:
    """Window-average strategy declines to impute with sparse history."""
    provider = _InMemoryState()
    config = WindowAverageImputationConfig(
        window_seconds=30,
        min_samples=2,
        max_gap_seconds=120,
    )
    strategy = WindowAverageImputation(config=config)
    reference_time = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
    reading = _make_reading(sensor_id=5, value=10.0, timestamp=reference_time)

    result = strategy.compute(sensor_id=reading.sensor_id, reading=reading, state=provider)

    assert result is None


def test_window_average_strategy_averages_recent_history() -> None:
    """Window-average strategy computes the mean of values inside the window."""
    provider = _InMemoryState()
    config = WindowAverageImputationConfig(
        window_seconds=15,
        min_samples=2,
        max_gap_seconds=120,
    )
    strategy = WindowAverageImputation(config=config)
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
    readings = [
        _make_reading(sensor_id=8, value=12.0, timestamp=base_time - 20),
        _make_reading(sensor_id=8, value=18.0, timestamp=base_time - 10),
        _make_reading(sensor_id=8, value=24.0, timestamp=base_time - 5),
    ]
    for item in readings:
        provider.update(sensor_id=item.sensor_id, reading=item)
    target = _make_reading(sensor_id=8, value=30.0, timestamp=base_time)

    result = strategy.compute(sensor_id=target.sensor_id, reading=target, state=provider)

    assert result is not None
    assert result == (18.0 + 24.0) / 2


def test_build_strategy_selects_linear_interpolation() -> None:
    """Factory returns linear extrapolation strategy when configured."""
    sensor_config = SensorConfig(
        units="C",
        range=None,  # type: ignore[arg-type]
        roc=None,  # type: ignore[arg-type]
        stuck=None,  # type: ignore[arg-type]
        imputation=LinearExtrapolationImputationConfig(window_seconds=180, max_gap_seconds=300),
    )

    strategy = build_imputation_strategy(sensor_config=sensor_config)

    assert isinstance(strategy, LinearExtrapolationImputation)


def test_linear_interpolation_extrapolates_from_recent_trend() -> None:
    """Linear extrapolation projects values from the latest trend."""
    provider = _InMemoryState()
    config = LinearExtrapolationImputationConfig(window_seconds=300, max_gap_seconds=180)
    strategy = LinearExtrapolationImputation(config=config)
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
    history = [
        _make_reading(sensor_id=15, value=10.0, timestamp=base_time - 120),
        _make_reading(sensor_id=15, value=14.0, timestamp=base_time - 60),
    ]
    for item in history:
        provider.update(sensor_id=item.sensor_id, reading=item)
    reading = _make_reading(sensor_id=15, value=0.0, timestamp=base_time)

    result = strategy.compute(sensor_id=reading.sensor_id, reading=reading, state=provider)

    assert result is not None
    # slope = (14-10)/60 => 0.0666..., extrapolate 60 seconds => 14 + 4 = 18
    assert result == 18.0


def test_linear_interpolation_respects_max_gap() -> None:
    """Linear extrapolation refuses to impute when the gap exceeds its limit."""
    provider = _InMemoryState()
    config = LinearExtrapolationImputationConfig(window_seconds=600, max_gap_seconds=120)
    strategy = LinearExtrapolationImputation(config=config)
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
    history = [
        _make_reading(sensor_id=33, value=5.0, timestamp=base_time - 600),
        _make_reading(sensor_id=33, value=7.0, timestamp=base_time - 300),
    ]
    for item in history:
        provider.update(sensor_id=item.sensor_id, reading=item)
    reading = _make_reading(sensor_id=33, value=0.0, timestamp=base_time)

    result = strategy.compute(sensor_id=reading.sensor_id, reading=reading, state=provider)

    assert result is None
