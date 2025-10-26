from pathlib import Path

import pytest

from dt.communication.dataclasses.preprocessing_config import (
    EWMASmoothingConfig,
    SensorValidationConfig,
)


def test_load_sensor_validation_config_defaults():
    """Validate that defaults are loaded as specified in the YAML config.

    Returns
    -------
    None
        The assertions raise if parsed defaults diverge from expectations.
    """
    config_path = Path(__file__).resolve().parents[3] / "dt" / "utils" / "preprocessing_config.yml"

    rules = SensorValidationConfig.load(str(config_path))

    assert rules.defaults.windows.small_sec == 60
    assert rules.defaults.scoring.weights.range_ok == 0.4

    temp_rules = rules.sensors["dht22.temperature"]
    assert temp_rules.range.min == -40.0
    assert temp_rules.range.max == 80.0
    assert temp_rules.roc.active_max_per_minute == 1.0


def test_apply_roc_overrides_switches_active_profile():
    """Ensure ROC overrides activate the targeted profile.

    Returns
    -------
    None
        Assertions fail when the override does not switch to the requested profile.
    """
    config_dict = {
        "defaults": {
            "windows": {"small_sec": 10, "medium_sec": 90, "big_sec": 180},
            "scoring": {
                "weights": {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2},
            },
        },
        "sensors": {
            "bh1750.lux": {
                "units": "lux",
                "range": {"min": 0, "max": 1000},
                "roc": {
                    "profiles": {
                        "indoor": {"max_per_minute": 10},
                        "outdoor": {"max_per_minute": 100},
                    },
                    "active_profile": "indoor",
                },
                "stuck": {"max_flat_seconds": 60},
            }
        },
    }
    rules = SensorValidationConfig.from_dict(config_dict)

    rules.apply_roc_overrides({"bh1750.lux": "outdoor"})

    lux_rules = rules.sensors["bh1750.lux"]
    assert lux_rules.roc.active_profile == "outdoor"
    assert lux_rules.roc.active_max_per_minute == 100.0


def test_apply_roc_overrides_rejects_unknown_sensor():
    """Confirm overrides fail fast for missing sensors.

    Returns
    -------
    None
        The context manager fails if the expected KeyError is not raised.
    """
    config_dict = {
        "defaults": {
            "windows": {"small_sec": 5, "medium_sec": 30, "big_sec": 60},
            "scoring": {"weights": {"range_ok": 0.6, "roc_ok": 0.3, "stuck_ok": 0.1}},
        },
        "sensors": {
            "custom.sensor": {
                "units": "%",
                "range": {"min": 10, "max": 90},
                "roc": {"max_per_minute": 7.5},
                "stuck": {"max_flat_seconds": 45},
            }
        },
    }
    rules = SensorValidationConfig.from_dict(config_dict)

    with pytest.raises(KeyError):
        rules.apply_roc_overrides({"missing.sensor": "profile"})


def test_roc_config_active_max_per_minute_falls_back_to_default():
    """Check that the default RoC limit is used when no profile is active.

    Returns
    -------
    None
        Asserts equality for the default RoC limit.
    """

    config = SensorValidationConfig.from_dict(
        {
            "defaults": {
                "windows": {"small_sec": 1, "medium_sec": 2, "big_sec": 3},
                "scoring": {"weights": {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2}},
            },
            "sensors": {
                "simple.sensor": {
                    "units": "ppm",
                    "range": {"min": 0, "max": 100},
                    "roc": {"max_per_minute": 4.5},
                    "stuck": {"max_flat_seconds": 10},
                }
            },
        }
    )

    assert config.sensors["simple.sensor"].roc.active_max_per_minute == 4.5


def test_set_active_profile_raises_for_missing_profile():
    """Ensure set_active_profile rejects profile names that are undefined.

    Returns
    -------
    None
        The context manager fails if a KeyError is not raised.
    """

    config = SensorValidationConfig.from_dict(
        {
            "defaults": {
                "windows": {"small_sec": 1, "medium_sec": 2, "big_sec": 3},
                "scoring": {"weights": {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2}},
            },
            "sensors": {
                "profiled.sensor": {
                    "units": "ppm",
                    "range": {"min": 0, "max": 100},
                    "roc": {
                        "profiles": {"indoor": {"max_per_minute": 5}},
                        "active_profile": "indoor",
                    },
                    "stuck": {"max_flat_seconds": 10},
                }
            },
        }
    )

    with pytest.raises(KeyError):
        config.sensors["profiled.sensor"].roc.set_active_profile("outdoor")


def test_apply_roc_overrides_requires_profiles():
    """Ensure overrides fail when sensor lacks profile definitions.

    Returns
    -------
    None
        The context manager fails if ValueError is not raised.
    """

    config = SensorValidationConfig.from_dict(
        {
            "defaults": {
                "windows": {"small_sec": 1, "medium_sec": 2, "big_sec": 3},
                "scoring": {"weights": {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2}},
            },
            "sensors": {
                "simple.sensor": {
                    "units": "ppm",
                    "range": {"min": 0, "max": 100},
                    "roc": {"max_per_minute": 4.5},
                    "stuck": {"max_flat_seconds": 10},
                }
            },
        }
    )

    with pytest.raises(ValueError):
        config.apply_roc_overrides({"simple.sensor": "indoor"})


def test_smoothing_config_parses_parameters():
    config = SensorValidationConfig.from_dict(
        {
            "defaults": {
                "windows": {"small_sec": 1, "medium_sec": 2, "big_sec": 3},
                "scoring": {"weights": {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2}},
            },
            "sensors": {
                "dht22.temperature": {
                    "units": "C",
                    "range": {"min": -10, "max": 50},
                    "roc": {"max_per_minute": 1.0},
                    "stuck": {"max_flat_seconds": 300},
                    "smoothing": {
                        "strategy": "ewma",
                        "alpha": 0.2,
                    },
                }
            },
        }
    )

    smoothing = config.sensors["dht22.temperature"].smoothing
    assert isinstance(smoothing, EWMASmoothingConfig)
    assert smoothing.alpha == 0.2


def test_smoothing_config_rejects_unknown_strategy():
    with pytest.raises(ValueError):
        SensorValidationConfig.from_dict(
            {
                "defaults": {
                    "windows": {"small_sec": 1, "medium_sec": 2, "big_sec": 3},
                    "scoring": {
                        "weights": {
                            "range_ok": 0.5,
                            "roc_ok": 0.3,
                            "stuck_ok": 0.2,
                        }
                    },
                },
                "sensors": {
                    "sensor.foo": {
                        "units": "C",
                        "range": {"min": 0, "max": 100},
                        "roc": {"max_per_minute": 1.0},
                        "stuck": {"max_flat_seconds": 60},
                        "smoothing": {"strategy": "unknown"},
                    }
                },
            }
        )
