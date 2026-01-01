from datetime import datetime, timedelta, timezone

from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics
from dt.data.preprocess.config.types import RangeConfig, RocConfig, StuckConfig
from dt.data.preprocess.stages.validation.checks import (
    check_range,
    check_rate_of_change,
    check_stuck,
)
from dt.data.preprocess.stages.validation.scoring import compute_dq_score


def test_compute_dq_score_respects_config_weights() -> None:
    """DQ score returns the weight of checks that passed."""
    weights = {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2}
    flags = {
        ValidationFlag.RANGE: False,
        ValidationFlag.RATE_OF_CHANGE: True,
        ValidationFlag.STUCK: True,
    }

    score = compute_dq_score(flags, weights)
    assert score == 0.5


def test_compute_dq_score_returns_full_score_when_all_checks_pass() -> None:
    """DQ score returns 1.0 when no validation flags are raised."""
    weights = {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2}
    flags = {
        ValidationFlag.RANGE: False,
        ValidationFlag.RATE_OF_CHANGE: False,
        ValidationFlag.STUCK: False,
    }

    score = compute_dq_score(flags, weights)
    assert score == 1.0


def test_compute_dq_score_returns_zero_when_all_checks_fail() -> None:
    """DQ score returns 0.0 when every validation flag is raised."""
    weights = {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2}
    flags = {
        ValidationFlag.RANGE: True,
        ValidationFlag.RATE_OF_CHANGE: True,
        ValidationFlag.STUCK: True,
    }

    score = compute_dq_score(flags, weights)
    assert score == 0.0


def test_compute_dq_score_handles_missing_weights() -> None:
    """DQ score collapses to 0 when weights are missing and some checks fail."""
    flags = {
        ValidationFlag.RANGE: False,
        ValidationFlag.RATE_OF_CHANGE: True,
        ValidationFlag.STUCK: False,
    }

    score = compute_dq_score(flags, {})
    assert score == 0.0


def test_check_range_flags_out_of_bounds_value() -> None:
    """Range validator rejects values falling outside configured bounds."""
    rule = RangeConfig(min=10.0, max=30.0)
    reading = RawSensorData(
        plant_id=1,
        sensor_id=10,
        timestamp=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc).timestamp(),
        value=35.0,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="range-fail",
    )

    is_valid, reason = check_range(reading=reading, rule=rule)
    assert is_valid is False
    assert reason is ValidationFlag.RANGE


def test_check_range_accepts_value_within_bounds() -> None:
    """Range validator accepts values located inside configured bounds."""
    rule = RangeConfig(min=10.0, max=30.0)
    reading = RawSensorData(
        plant_id=1,
        sensor_id=10,
        timestamp=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc).timestamp(),
        value=25.0,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="range-pass",
    )

    is_valid, reason = check_range(reading=reading, rule=rule)
    assert is_valid is True
    assert reason is ValidationFlag.VALID


def test_check_rate_of_change_flags_excessive_delta() -> None:
    """Rate-of-change validator flags deltas exceeding the configured limit."""
    rule = RocConfig(max_per_minute=2.0, profiles={}, active_profile=None)
    previous = RawSensorData(
        plant_id=1,
        sensor_id=10,
        timestamp=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc).timestamp(),
        value=20.0,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="roc-prev",
    )
    reading = RawSensorData(
        plant_id=1,
        sensor_id=10,
        timestamp=datetime(2025, 1, 1, 12, 0, 30, tzinfo=timezone.utc).timestamp(),
        value=26.0,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="roc-read",
    )

    is_valid, reason = check_rate_of_change(reading=reading, previous_valid=previous, rule=rule)
    assert is_valid is False
    assert reason is ValidationFlag.RATE_OF_CHANGE


def test_check_rate_of_change_accepts_delta_within_limit() -> None:
    """Rate-of-change validator approves deltas inside the configured limit."""
    rule = RocConfig(max_per_minute=4.0, profiles={}, active_profile=None)
    previous = RawSensorData(
        plant_id=1,
        sensor_id=11,
        timestamp=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc).timestamp(),
        value=20.0,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="roc-prev-ok",
    )
    reading = RawSensorData(
        plant_id=1,
        sensor_id=11,
        timestamp=datetime(2025, 1, 1, 12, 0, 30, tzinfo=timezone.utc).timestamp(),
        value=21.5,
        unit="C",
        topic=Topics.TEMPERATURE,
        correlation_id="roc-read-ok",
    )

    is_valid, reason = check_rate_of_change(reading=reading, previous_valid=previous, rule=rule)
    assert is_valid is True
    assert reason is ValidationFlag.VALID


def test_check_stuck_flags_flatline_beyond_threshold() -> None:
    """Stuck validator identifies flatlined windows exceeding the threshold."""
    rule = StuckConfig(max_flat_seconds=45)
    base_time = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    history = [
        RawSensorData(
            plant_id=1,
            sensor_id=12,
            timestamp=(base_time + timedelta(seconds=offset)).timestamp(),
            value=18.0,
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id=f"stuck-{offset}",
        )
        for offset in (0, 30, 60)
    ]

    is_valid, reason = check_stuck(history=history, rule=rule)
    assert is_valid is False
    assert reason is ValidationFlag.STUCK


def test_check_stuck_accepts_varying_values() -> None:
    """Stuck validator passes windows with sufficient movement."""
    rule = StuckConfig(max_flat_seconds=45)
    base_time = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    history = [
        RawSensorData(
            plant_id=1,
            sensor_id=13,
            timestamp=(base_time + timedelta(seconds=offset)).timestamp(),
            value=18.0 + (offset / 100),
            unit="C",
            topic=Topics.TEMPERATURE,
            correlation_id=f"stuck-ok-{offset}",
        )
        for offset in (0, 30, 60)
    ]

    is_valid, reason = check_stuck(history=history, rule=rule)
    assert is_valid is True
    assert reason is ValidationFlag.VALID

