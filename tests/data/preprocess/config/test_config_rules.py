from pathlib import Path
from unittest.mock import patch

import pytest
from cattrs.errors import ClassValidationError

from dt.communication.adapters.registry import load
from dt.data.preprocess.config.manager import ConfigurationManager
from dt.data.preprocess.config.serialization import ensure_config_serialization
from dt.data.preprocess.config.types import EWMASmoothingConfig, RocConfig, RocProfile, SystemConfig


def test_load_sensor_validation_config_defaults() -> None:
    """Validate that defaults are loaded as specified in preprocessing_config.yml.

    Returns
    -------
    None
        The assertions raise if parsed defaults diverge from expectations.
    """
    config_path = Path(__file__).resolve().parents[4] / "dt" / "utils" / "preprocessing_config.yml"

    with patch("dt.data.preprocess.config.manager.DatabaseApiClient") as mock_db_client:
        mock_db_client.return_value.list_sensors.return_value = []
        manager = ConfigurationManager(str(config_path))

    assert manager.config.system.windows.small_sec == 60
    assert manager.config.system.weights.range_ok == 0.4

    temp_config = manager.get_sensor_config("dht22.temperature")
    assert temp_config.validation.range.min == -40.0
    assert temp_config.validation.range.max == 80.0
    assert temp_config.validation.roc.active_max_per_minute == 1.0


def test_set_active_profile_switches_active_profile() -> None:
    """Ensure ROC overrides activate the targeted profile.

    Returns
    -------
    None
        Assertions fail when the override does not switch to the requested profile.
    """
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
    """Check that the default RoC limit is used when no profile is active.

    Returns
    -------
    None
        Asserts equality for the default RoC limit.
    """
    roc = RocConfig(max_per_minute=4.5, profiles={}, active_profile=None)
    assert roc.active_max_per_minute == 4.5


def test_set_active_profile_raises_for_missing_profile() -> None:
    """Ensure set_active_profile rejects profile names that are undefined.

    Returns
    -------
    None
        The context manager fails if a KeyError is not raised.
    """
    roc = RocConfig(
        max_per_minute=None,
        profiles={"indoor": RocProfile(max_per_minute=5)},
        active_profile="indoor",
    )

    with pytest.raises(KeyError):
        roc.set_active_profile("outdoor")


def test_smoothing_config_parses_parameters() -> None:
    """Parse EWMA smoothing parameters into typed config objects.

    Returns
    -------
    None
        Assertions fail if polymorphic config loading changes.
    """
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
    """Reject smoothing strategies that are not registered.

    Returns
    -------
    None
        The test fails if unknown strategies stop raising validation errors.
    """
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
