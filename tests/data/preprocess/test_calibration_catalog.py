from pathlib import Path

import pytest
import yaml

from dt.data.preprocess.calibration import (ProfileConfiguration,
                                            load_profile_configuration)
from dt.data.preprocess.configuration.catalog import CalibrationCatalog
from dt.data.preprocess.configuration.profiles import (
    AffineCalibrationParameters, MinMaxNormalizationParameters)


@pytest.fixture
def catalog(test_config_path) -> CalibrationCatalog:
    profiles = load_profile_configuration(test_config_path)
    catalog = CalibrationCatalog(profiles)
    return catalog


def test_get_calibration_returns_sensor_override(catalog: CalibrationCatalog) -> None:

    profile = catalog.get_calibration("sensors.greenhouse.dht22.001.temperature")
    assert profile.profile_id == "calibration.dht22.temperature.greenhouse-001"
    assert profile.strategy == "affine"
    assert isinstance(profile.parameters, AffineCalibrationParameters)
    assert profile.parameters.offset == -0.2


def test_get_calibration_returns_default_when_not_overridden(catalog: CalibrationCatalog) -> None:
    catalog.register_sensor("sensors.greenhouse.dht22.002.temperature", "dht22.temperature")

    profile = catalog.get_calibration("sensors.greenhouse.dht22.002.temperature")
    assert profile.profile_id == "calibration.dht22.temperature.test"
    assert isinstance(profile.parameters, AffineCalibrationParameters)
    assert profile.parameters.scale == 1.05
    assert profile.parameters.offset == -0.5


def test_get_normalization_returns_override_and_default(catalog: CalibrationCatalog) -> None:

    override_profile = catalog.get_normalization("sensors.greenhouse.bh1750.001")
    assert override_profile.profile_id == "normalization.bh1750.lux.greenhouse-001"
    assert isinstance(override_profile.parameters, MinMaxNormalizationParameters)
    assert override_profile.parameters.input_max == 20000.0
    assert override_profile.parameters.clip is True

    catalog.register_sensor("sensors.greenhouse.bh1750.002", "bh1750.lux")
    default_profile = catalog.get_normalization("sensors.greenhouse.bh1750.002")
    assert default_profile.profile_id == "normalization.bh1750.lux.test"
    assert isinstance(default_profile.parameters, MinMaxNormalizationParameters)
    assert default_profile.parameters.input_max == 65535.0


def test_missing_sensor_registration_raises(catalog) -> None:

    with pytest.raises(KeyError):
        catalog.get_calibration("sensors.unknown.device")


def test_registered_sensors_not_configured_raises(catalog: CalibrationCatalog) -> None:
    """Test that requesting calibration/normalization for a registered sensor
    and a defined profile for either calibration or normalization but not both raises a KeyError.
    """

    # bh1750.lux is defined as a sensor but has no calibration profile
    # sensors.greenhouse.bh1750.001 Has an normalization override
    catalog.register_sensor("sensors.greenhouse.bh1750.002", "bh1750.lux")

    with pytest.raises(KeyError):
        catalog.get_calibration("sensors.greenhouse.bh1750.001")

    catalog.get_normalization("sensors.greenhouse.bh1750.002")  # Default exists
    catalog.get_normalization("sensors.greenhouse.bh1750.001")  # Override profile exists


def test_reload_updates_profiles_and_preserves_registrations(
    test_config_path, catalog: CalibrationCatalog
) -> None:
    raw = yaml.safe_load(Path(test_config_path).read_text())
    raw["calibration_profiles"]["overrides"]["sensors.greenhouse.dht22.001.temperature"][
        "parameters"
    ]["offset"] = -0.3
    new_profiles = ProfileConfiguration.from_dict(raw)

    # Previously registered sensors should still be available
    catalog.register_sensor("sensors.greenhouse.dht22.002.temperature", "dht22.temperature")
    catalog.reload(new_profiles)

    override_profile = catalog.get_calibration("sensors.greenhouse.dht22.001.temperature")
    assert isinstance(override_profile.parameters, AffineCalibrationParameters)
    assert override_profile.parameters.offset == -0.3
    default_profile = catalog.get_calibration("sensors.greenhouse.dht22.002.temperature")
    assert isinstance(default_profile.parameters, AffineCalibrationParameters)
    assert default_profile.parameters.offset == -0.5


def test_reload_resets_sensor_mapping_when_explicit_map_provided(
    catalog: CalibrationCatalog, test_config_path: str
) -> None:

    catalog.register_sensor("sensors.greenhouse.dht22.002.temperature", "dht22.temperature")
    profiles = load_profile_configuration(test_config_path)
    catalog.reload(profiles, sensor_types={})

    with pytest.raises(KeyError):
        catalog.get_calibration("sensors.greenhouse.dht22.002.temperature")
