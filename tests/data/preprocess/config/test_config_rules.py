from pathlib import Path

import pytest
from cattrs.errors import ClassValidationError

from dt.communication.adapters.registry import load
from dt.data.preprocess.config.manager import ConfigurationManager
from dt.data.preprocess.config.serialization import ensure_config_serialization
from dt.data.preprocess.config.types import (EWMASmoothingConfig, RocConfig,
                                             RocProfile, SystemConfig)


def test_load_sensor_validation_config_defaults(configure_preprocess_db_client) -> None:
    """Validate that defaults are loaded as specified in preprocessing_config.yml."""
    config_path = Path(__file__).resolve().parents[4] / "dt" / "utils" / "preprocessing_config.yml"

    manager = ConfigurationManager(str(config_path))

    assert manager.config.system.windows.small_sec == 60
    assert manager.config.system.weights.range_ok == 0.4

    temp_config = manager.get_sensor_config("dht22.temperature")
    assert temp_config.validation.range.min == 0
    assert temp_config.validation.range.max == 50
    assert temp_config.validation.roc.active_max_per_minute == 5.0


def test_set_active_profile_switches_active_profile() -> None:
    """Ensure ROC overrides activate the targeted profile."""
    roc = RocConfig(
        max_per_minute=None,
        profiles={
            "indoor": RocProfile(max_per_minute=10),
            "outdoor": RocProfile(max_per_minute=100),
        },
        active_profile="indoor",
    )

    roc.set_active_profile("outdoor")

    assert roc.active_profile == "outdoor"
    assert roc.active_max_per_minute == 100.0


def test_roc_config_active_max_per_minute_falls_back_to_default() -> None:
    """Check that the default RoC limit is used when no profile is active."""
    roc = RocConfig(max_per_minute=4.5, profiles={}, active_profile=None)
    assert roc.active_max_per_minute == 4.5


def test_set_active_profile_raises_for_missing_profile() -> None:
    """Ensure set_active_profile rejects profile names that are undefined."""
    roc = RocConfig(
        max_per_minute=None,
        profiles={"indoor": RocProfile(max_per_minute=5)},
        active_profile="indoor",
    )

    with pytest.raises(KeyError):
        roc.set_active_profile("outdoor")


def test_smoothing_config_parses_parameters() -> None:
    """Parse EWMA smoothing parameters into typed config objects."""
    ensure_config_serialization()
    config = load(
        "generic",
        SystemConfig,
        {
            "system": {
                "windows": {"small_sec": 1, "medium_sec": 2, "big_sec": 3},
                "weights": {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2},
            },
            "sensors": {
                "dht22.temperature": {
                    "units": "C",
                    "smoothing": {"strategy": "ewma", "alpha": 0.2},
                }
            },
        },
    )

    smoothing = config.sensors["dht22.temperature"].smoothing
    assert isinstance(smoothing, EWMASmoothingConfig)
    assert smoothing.alpha == 0.2


def test_smoothing_config_rejects_unknown_strategy() -> None:
    """Reject smoothing strategies that are not registered."""
    ensure_config_serialization()
    with pytest.raises(ClassValidationError):
        load(
            "generic",
            SystemConfig,
            {
                "system": {
                    "windows": {"small_sec": 1, "medium_sec": 2, "big_sec": 3},
                    "weights": {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2},
                },
                "sensors": {"sensor.foo": {"units": "C", "smoothing": {"strategy": "unknown"}}},
            },
        )


def test_imputation_config_parses_forward_fill_parameters() -> None:
    """Parse forward fill imputation parameters into typed config objects."""
    ensure_config_serialization()
    config = load(
        "generic",
        SystemConfig,
        {
            "system": {
                "windows": {"small_sec": 1, "medium_sec": 2, "big_sec": 3},
                "weights": {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2},
            },
            "sensors": {
                "sensor.temp": {
                    "units": "C",
                    "imputation": {
                        "strategy": "forward_fill_with_decay",
                        "max_gap_seconds": 180,
                        "decay_seconds": 60,
                        "baseline": 12.5,
                    },
                }
            },
        },
    )

    imputation = config.sensors["sensor.temp"].imputation
    assert imputation.strategy == "forward_fill_with_decay"
    assert imputation.max_gap_seconds == 180
    assert imputation.decay_seconds == 60
    assert imputation.baseline == 12.5


def test_imputation_config_parses_window_average_parameters() -> None:
    """Parse window average imputation parameters into typed config objects."""
    ensure_config_serialization()
    config = load(
        "generic",
        SystemConfig,
        {
            "system": {
                "windows": {"small_sec": 1, "medium_sec": 2, "big_sec": 3},
                "weights": {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2},
            },
            "sensors": {
                "sensor.temp": {
                    "units": "C",
                    "imputation": {
                        "strategy": "window_average",
                        "window_seconds": 90,
                        "min_samples": 3,
                        "max_gap_seconds": 600,
                    },
                }
            },
        },
    )

    imputation = config.sensors["sensor.temp"].imputation
    assert imputation.strategy == "window_average"
    assert imputation.window_seconds == 90
    assert imputation.min_samples == 3
    assert imputation.max_gap_seconds == 600


def test_imputation_config_parses_linear_extrapolation_parameters() -> None:
    """Parse linear extrapolation parameters into typed config objects."""
    ensure_config_serialization()
    config = load(
        "generic",
        SystemConfig,
        {
            "system": {
                "windows": {"small_sec": 1, "medium_sec": 2, "big_sec": 3},
                "weights": {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2},
            },
            "sensors": {
                "sensor.temp": {
                    "units": "C",
                    "imputation": {
                        "strategy": "linear_extrapolation",
                        "window_seconds": 120,
                        "max_gap_seconds": 300,
                    },
                }
            },
        },
    )

    imputation = config.sensors["sensor.temp"].imputation
    assert imputation.strategy == "linear_extrapolation"
    assert imputation.window_seconds == 120
    assert imputation.max_gap_seconds == 300


def test_imputation_config_rejects_unknown_strategy() -> None:
    """Reject imputation strategies that are not registered."""
    ensure_config_serialization()
    with pytest.raises(ClassValidationError):
        load(
            "generic",
            SystemConfig,
            {
                "system": {
                    "windows": {"small_sec": 1, "medium_sec": 2, "big_sec": 3},
                    "weights": {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2},
                },
                "sensors": {"sensor.foo": {"units": "C", "imputation": {"strategy": "unknown"}}},
            },
        )


def test_calibration_config_parses_affine_parameters() -> None:
    """Parse affine calibration parameters into typed config objects."""
    ensure_config_serialization()
    config = load(
        "generic",
        SystemConfig,
        {
            "system": {
                "windows": {"small_sec": 1, "medium_sec": 2, "big_sec": 3},
                "weights": {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2},
            },
            "sensors": {
                "sensor.temp": {
                    "units": "C",
                    "calibration": {"strategy": "affine", "scale": 1.2, "offset": -0.5},
                }
            },
        },
    )

    calibration = config.sensors["sensor.temp"].calibration
    assert calibration.strategy == "affine"
    assert calibration.scale == 1.2
    assert calibration.offset == -0.5


def test_calibration_config_parses_identity_strategy() -> None:
    """Parse identity calibration into typed config objects."""
    ensure_config_serialization()
    config = load(
        "generic",
        SystemConfig,
        {
            "system": {
                "windows": {"small_sec": 1, "medium_sec": 2, "big_sec": 3},
                "weights": {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2},
            },
            "sensors": {"sensor.temp": {"units": "C", "calibration": {"strategy": "identity"}}},
        },
    )

    calibration = config.sensors["sensor.temp"].calibration
    assert calibration.strategy == "identity"


def test_calibration_config_parses_piecewise_lookup_segments() -> None:
    """Parse piecewise lookup calibration segments into typed config objects."""
    ensure_config_serialization()
    config = load(
        "generic",
        SystemConfig,
        {
            "system": {
                "windows": {"small_sec": 1, "medium_sec": 2, "big_sec": 3},
                "weights": {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2},
            },
            "sensors": {
                "sensor.temp": {
                    "units": "C",
                    "calibration": {
                        "strategy": "piecewise_lookup",
                        "segments": [
                            {"input_min": 0.0, "input_max": 1.0, "output": 10.0},
                            {"input_min": 1.0, "input_max": 2.0, "output": 20.0},
                        ],
                    },
                }
            },
        },
    )

    calibration = config.sensors["sensor.temp"].calibration
    assert calibration.strategy == "piecewise_lookup"
    assert len(calibration.segments) == 2
    assert calibration.segments[0].input_min == 0.0
    assert calibration.segments[1].output == 20.0


def test_calibration_config_rejects_unknown_strategy() -> None:
    """Reject calibration strategies that are not registered."""
    ensure_config_serialization()
    with pytest.raises(ClassValidationError):
        load(
            "generic",
            SystemConfig,
            {
                "system": {
                    "windows": {"small_sec": 1, "medium_sec": 2, "big_sec": 3},
                    "weights": {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2},
                },
                "sensors": {"sensor.foo": {"units": "C", "calibration": {"strategy": "unknown"}}},
            },
        )


def test_normalization_config_parses_min_max_parameters() -> None:
    """Parse min-max normalization parameters into typed config objects."""
    ensure_config_serialization()
    config = load(
        "generic",
        SystemConfig,
        {
            "system": {
                "windows": {"small_sec": 1, "medium_sec": 2, "big_sec": 3},
                "weights": {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2},
            },
            "sensors": {
                "sensor.temp": {
                    "units": "C",
                    "normalization": {
                        "strategy": "min_max",
                        "input_min": 0.0,
                        "input_max": 100.0,
                        "output_min": -1.0,
                        "output_max": 1.0,
                        "clip": False,
                    },
                }
            },
        },
    )

    normalization = config.sensors["sensor.temp"].normalization
    assert normalization.strategy == "min_max"
    assert normalization.input_min == 0.0
    assert normalization.input_max == 100.0
    assert normalization.output_min == -1.0
    assert normalization.output_max == 1.0
    assert normalization.clip is False


def test_normalization_config_parses_identity_strategy() -> None:
    """Parse identity normalization into typed config objects."""
    ensure_config_serialization()
    config = load(
        "generic",
        SystemConfig,
        {
            "system": {
                "windows": {"small_sec": 1, "medium_sec": 2, "big_sec": 3},
                "weights": {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2},
            },
            "sensors": {"sensor.temp": {"units": "C", "normalization": {"strategy": "identity"}}},
        },
    )

    normalization = config.sensors["sensor.temp"].normalization
    assert normalization.strategy == "identity"


def test_normalization_config_rejects_unknown_strategy() -> None:
    """Reject normalization strategies that are not registered."""
    ensure_config_serialization()
    with pytest.raises(ClassValidationError):
        load(
            "generic",
            SystemConfig,
            {
                "system": {
                    "windows": {"small_sec": 1, "medium_sec": 2, "big_sec": 3},
                    "weights": {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2},
                },
                "sensors": {"sensor.foo": {"units": "C", "normalization": {"strategy": "unknown"}}},
            },
        )
