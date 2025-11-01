import pytest

from dt.data.preprocess.configuration.profiles import (
    AffineCalibrationParameters, MinMaxNormalizationParameters,
    ProfileConfiguration, load_profile_configuration)


@pytest.fixture
def profiles(test_config_path) -> ProfileConfiguration:
    profiles = load_profile_configuration(test_config_path)
    return profiles


def test_calibration_overrides_merge_with_defaults(profiles: ProfileConfiguration) -> None:

    temp_default = profiles.calibration.defaults["dht22.temperature"]
    assert temp_default.profile_id == "calibration.dht22.temperature.test"
    assert temp_default.strategy == "affine"
    assert isinstance(temp_default.parameters, AffineCalibrationParameters)
    assert temp_default.parameters.scale == 1.05
    assert temp_default.parameters.offset == -0.5

    temp_override = profiles.calibration.overrides["sensors.greenhouse.dht22.001.temperature"]
    assert temp_override.sensor_type == "dht22.temperature"
    assert temp_override.profile.profile_id == "calibration.dht22.temperature.greenhouse-001"
    assert temp_override.profile.strategy == "affine"
    assert isinstance(temp_override.profile.parameters, AffineCalibrationParameters)
    assert temp_override.profile.parameters.scale == 1.05
    assert temp_override.profile.parameters.offset == -0.2


def test_normalization_overrides_merge_with_defaults(profiles: ProfileConfiguration) -> None:

    lux_default = profiles.normalization.defaults["bh1750.lux"]
    assert lux_default.profile_id == "normalization.bh1750.lux.test"
    assert lux_default.strategy == "min_max"
    assert isinstance(lux_default.parameters, MinMaxNormalizationParameters)
    assert lux_default.parameters.input_min == 0.0
    assert lux_default.parameters.input_max == 65535.0
    assert lux_default.parameters.output_min == 0.0
    assert lux_default.parameters.output_max == 1.0
    assert lux_default.parameters.clip is True

    lux_override = profiles.normalization.overrides["sensors.greenhouse.bh1750.001"]
    assert lux_override.sensor_type == "bh1750.lux"
    assert lux_override.profile.profile_id == "normalization.bh1750.lux.greenhouse-001"
    assert isinstance(lux_override.profile.parameters, MinMaxNormalizationParameters)
    assert lux_override.profile.parameters.input_min == 0.0
    assert lux_override.profile.parameters.input_max == 20000.0
    assert lux_override.profile.parameters.output_max == 1.0
    assert lux_override.profile.parameters.clip is True


def test_registered_sensors_not_configured_raises(profiles: ProfileConfiguration) -> None:

    # bh1750 lux has no calibration profile configured but has a normalization/override profile
    profiles.normalization.defaults["bh1750.lux"]
    profiles.normalization.overrides["sensors.greenhouse.bh1750.001"]

    with pytest.raises(KeyError):
        # TODO: We should set the IDENTITY strategy as default to avoid this error
        _ = profiles.calibration.defaults["bh1750.lux"]
