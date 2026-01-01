from dt.communication.adapters.registry import load
from dt.data.preprocess.config.serialization import ensure_config_serialization
from dt.data.preprocess.config.types import (
    AffineCalibrationConfig,
    EWMASmoothingConfig,
    MinMaxNormalizationConfig,
    PassThroughSmoothingConfig,
    PiecewiseLookupCalibrationConfig,
    SystemConfig,
    WindowAverageImputationConfig,
)


def test_config_loads_polymorphic_strategies() -> None:
    """Different strategy blocks load into the expected config dataclasses."""
    ensure_config_serialization()

    data = {
        "system": {
            "windows": {"small_sec": 60, "medium_sec": 300, "big_sec": 1000},
            "weights": {"range_ok": 0.4, "roc_ok": 0.4, "stuck_ok": 0.2},
        },
        "templates": {},
        "sensors": {
            "sensor.affine": {
                "units": "C",
                "calibration": {"strategy": "affine", "scale": 2.0, "offset": 5.0},
            },
            "sensor.lookup": {
                "units": "C",
                "calibration": {
                    "strategy": "piecewise_lookup",
                    "segments": [
                        {"input_min": 0, "input_max": 10, "output": 5},
                        {"input_min": 10, "input_max": 20, "output": 15},
                    ],
                },
            },
            "sensor.ewma": {"units": "V", "smoothing": {"strategy": "ewma", "alpha": 0.1}},
            "sensor.passthrough": {"units": "V", "smoothing": {"strategy": "pass_through"}},
            "sensor.imputation": {
                "units": "V",
                "imputation": {"strategy": "window_average", "window_seconds": 120},
            },
        },
    }

    config = load("generic", SystemConfig, data)

    affine_sensor = config.sensors["sensor.affine"]
    assert isinstance(affine_sensor.calibration, AffineCalibrationConfig)
    assert affine_sensor.calibration.scale == 2.0
    assert affine_sensor.calibration.offset == 5.0

    lookup_sensor = config.sensors["sensor.lookup"]
    assert isinstance(lookup_sensor.calibration, PiecewiseLookupCalibrationConfig)
    assert len(lookup_sensor.calibration.segments) == 2
    assert lookup_sensor.calibration.segments[1].output == 15.0

    ewma_sensor = config.sensors["sensor.ewma"]
    assert isinstance(ewma_sensor.smoothing, EWMASmoothingConfig)
    assert ewma_sensor.smoothing.alpha == 0.1

    pass_through_sensor = config.sensors["sensor.passthrough"]
    assert isinstance(pass_through_sensor.smoothing, PassThroughSmoothingConfig)

    imputation_sensor = config.sensors["sensor.imputation"]
    assert isinstance(imputation_sensor.imputation, WindowAverageImputationConfig)
    assert imputation_sensor.imputation.window_seconds == 120


def test_config_loads_normalization_defaults() -> None:
    ensure_config_serialization()
    data = {
        "system": {
            "windows": {"small_sec": 60, "medium_sec": 300, "big_sec": 1000},
            "weights": {"range_ok": 0.4, "roc_ok": 0.4, "stuck_ok": 0.2},
        },
        "sensors": {
            "sensor.norm": {
                "units": "N",
                "normalization": {"strategy": "min_max", "input_min": 0, "input_max": 100},
            }
        },
    }
    config = load("generic", SystemConfig, data)
    sensor = config.sensors["sensor.norm"]
    assert isinstance(sensor.normalization, MinMaxNormalizationConfig)
    assert sensor.normalization.input_max == 100.0
    assert sensor.normalization.output_max == 1.0


def test_config_loads_nested_validation_config() -> None:
    ensure_config_serialization()
    data = {
        "system": {
            "windows": {"small_sec": 60, "medium_sec": 300, "big_sec": 1000},
            "weights": {"range_ok": 0.4, "roc_ok": 0.4, "stuck_ok": 0.2},
        },
        "sensors": {
            "sensor.val": {
                "units": "K",
                "validation": {
                    "range": {"min": 0, "max": 100},
                    "roc": {"max_per_minute": 5.0},
                    "stuck": {"max_flat_seconds": 600},
                },
            }
        },
    }
    config = load("generic", SystemConfig, data)
    validation = config.sensors["sensor.val"].validation
    assert validation.range.min == 0.0
    assert validation.roc.max_per_minute == 5.0
    assert validation.stuck.max_flat_seconds == 600
