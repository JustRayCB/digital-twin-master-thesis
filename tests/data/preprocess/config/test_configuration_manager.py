import copy

import pytest
import yaml
from cattrs.errors import ClassValidationError

from dt.communication.topics import Topics
from dt.data.preprocess.config.manager import ConfigurationManager
from dt.data.preprocess.config.types import (
    AffineCalibrationConfig,
    MinMaxNormalizationConfig,
)
from dt.data.preprocess.stages.calibration import AffineCalibration as ExecutableAffine
from dt.data.preprocess.stages.calibration import (
    IdentityCalibration as ExecutableIdentityCalibration,
)
from dt.data.preprocess.stages.imputation import ForwardFillWithDecay
from dt.data.preprocess.stages.normalization import (
    IdentityNormalization,
    MinMaxNormalization,
)
from dt.data.preprocess.stages.smoothing import EWMASmoothing, PassThroughSmoothing


def write_config(tmp_path, config_data: dict[str, object], filename: str) -> str:
    """Write a config dictionary to a named temp file and return the path."""
    config_path = tmp_path / filename
    config_path.write_text(yaml.safe_dump(config_data))
    return str(config_path)


def write_default_config_file(tmp_path, config_manager_defaults) -> str:
    """Write the shared configuration-manager test config and return its path."""
    config_data = copy.deepcopy(config_manager_defaults)
    config_data["templates"] = {
        "temp_sensor": {
            "units": "C",
            "calibration": {"strategy": "affine", "scale": 1.0, "offset": 0.0},
            "validation": {"range": {"min": -10, "max": 50}},
        }
    }
    config_data["sensors"] = {
        "sensor.standard": {"template": "temp_sensor"},
        "sensor.calibrated": {
            "template": "temp_sensor",
            "calibration": {"strategy": "affine", "offset": 2.5},
        },
        "sensor.custom": {
            "units": "V",
            "normalization": {"strategy": "min_max", "input_max": 10.0},
        },
    }

    return write_config(tmp_path, config_data, "test_config.yml")


def test_sensor_inherits_from_template(tmp_path, config_manager_defaults) -> None:
    """Sensor inherits defaults from its referenced template."""
    manager = ConfigurationManager(
        write_default_config_file(tmp_path, config_manager_defaults)
    )
    config = manager.get_sensor_config("sensor.standard")

    assert config.units == "C"
    assert isinstance(config.calibration, AffineCalibrationConfig)
    assert config.calibration.scale == 1.0
    assert config.calibration.offset == 0.0
    assert config.validation.range.min == -10


def test_sensor_override_merges_with_template(
    tmp_path, config_manager_defaults
) -> None:
    """Per-sensor overrides should replace template fields."""
    manager = ConfigurationManager(
        write_default_config_file(tmp_path, config_manager_defaults)
    )
    config = manager.get_sensor_config("sensor.calibrated")

    assert config.units == "C"
    assert config.calibration.scale == 1.0
    assert config.calibration.offset == 2.5


def test_sensor_without_template_loads_standalone_config(
    tmp_path, config_manager_defaults
) -> None:
    """Standalone sensors can define strategy blocks without templates."""
    manager = ConfigurationManager(
        write_default_config_file(tmp_path, config_manager_defaults)
    )
    config = manager.get_sensor_config("sensor.custom")

    assert config.units == "V"
    assert isinstance(config.normalization, MinMaxNormalizationConfig)
    assert config.normalization.input_max == 10.0


def test_sensor_config_objects_are_cached(tmp_path, config_manager_defaults) -> None:
    """ConfigurationManager caches loaded SensorConfig objects."""
    manager = ConfigurationManager(
        write_default_config_file(tmp_path, config_manager_defaults)
    )
    first = manager.get_sensor_config("sensor.standard")
    second = manager.get_sensor_config("sensor.standard")
    assert first is second


def test_unknown_sensor_raises_key_error(tmp_path, config_manager_defaults) -> None:
    """Unknown sensor keys raise KeyError."""
    manager = ConfigurationManager(
        write_default_config_file(tmp_path, config_manager_defaults)
    )
    with pytest.raises(KeyError):
        manager.get_sensor_config("sensor.ghost")


def test_unknown_template_raises_error(tmp_path, config_manager_defaults) -> None:
    """Unknown templates referenced by sensors raise ValueError."""
    config_data = config_manager_defaults
    config_data["sensors"] = {"broken": {"template": "missing"}}
    path = write_config(tmp_path, config_data, "broken.yml")

    manager = ConfigurationManager(path)
    with pytest.raises(ValueError, match="unknown template"):
        manager.get_sensor_config("broken")


def test_profile_ids_reflect_overrides(tmp_path, config_manager_defaults) -> None:
    """Profile IDs encode which blocks were overridden."""
    manager = ConfigurationManager(
        write_default_config_file(tmp_path, config_manager_defaults)
    )

    standard = manager.get_sensor_config("sensor.standard")
    assert standard.calibration_profile_id == "temp_sensor"
    assert standard.normalization_profile_id == "temp_sensor"

    calibrated = manager.get_sensor_config("sensor.calibrated")
    assert calibrated.calibration_profile_id == "temp_sensor:sensor.calibrated-custom"
    assert calibrated.normalization_profile_id == "temp_sensor"

    custom = manager.get_sensor_config("sensor.custom")
    assert custom.normalization_profile_id == "standalone:sensor.custom"
    assert custom.calibration_profile_id == "default"


def test_resolve_sensor_config_maps_db_id_to_config_key(
    tmp_path,
    config_manager_defaults,
    sensor_registry,
    configure_preprocess_db_client,
) -> None:
    """resolve_sensor_config maps DB sensor IDs back to configured sensor keys."""
    sensor = sensor_registry["register"]("sensor.standard")

    manager = ConfigurationManager(
        write_default_config_file(tmp_path, config_manager_defaults)
    )
    sensor_key, sensor_config = manager.resolve_sensor_config(
        plant_id=sensor.plant_id, sensor_id=sensor.id, topic=Topics.TEMPERATURE
    )

    assert sensor_key == "sensor.standard"
    assert sensor_config.units == "C"


def test_resolve_sensor_config_falls_back_to_generic_key(
    tmp_path,
    config_manager_defaults,
    sensor_registry,
    configure_preprocess_db_client,
) -> None:
    """resolve_sensor_config falls back to generic sensor keys when device keys missing."""
    config_data = config_manager_defaults
    config_data["templates"] = {
        "temp_sensor": {"units": "C", "validation": {"range": {"min": -10, "max": 50}}}
    }
    config_data["sensors"] = {"dht22.temperature": {"template": "temp_sensor"}}
    path = write_config(tmp_path, config_data, "generic_only.yml")

    sensor = sensor_registry["register"]("sensors.basil.dht22.001.temperature")

    manager = ConfigurationManager(path)
    sensor_key, sensor_config = manager.resolve_sensor_config(
        plant_id=sensor.plant_id, sensor_id=sensor.id, topic=Topics.TEMPERATURE
    )

    assert sensor_key == "dht22.temperature"
    assert sensor_config.units == "C"


def test_resolve_sensor_config_rejects_numeric_yaml_keys(
    tmp_path,
    config_manager_defaults,
    sensor_registry,
    configure_preprocess_db_client,
) -> None:
    """Numeric sensor keys in YAML are rejected to prevent ambiguous resolution."""
    config_data = config_manager_defaults
    config_data["sensors"] = {"7": {"units": "C"}}
    path = write_config(tmp_path, config_data, "numeric_key.yml")

    sensor = sensor_registry["register"]("sensors.basil.dht22.001.temperature")

    manager = ConfigurationManager(path)
    with pytest.raises(KeyError):
        manager.resolve_sensor_config(
            plant_id=sensor.plant_id, sensor_id=sensor.id, topic=Topics.TEMPERATURE
        )


def test_template_override_preserves_nested_fields(
    tmp_path, config_manager_defaults
) -> None:
    """Nested overrides should preserve template values when fields are omitted."""
    config_data = config_manager_defaults
    config_data["templates"] = {
        "temp_sensor": {
            "units": "C",
            "validation": {"range": {"min": -10, "max": 50}},
        }
    }
    config_data["sensors"] = {
        "sensor.partial": {
            "template": "temp_sensor",
            "validation": {"roc": {"max_per_minute": 1.5}},
        }
    }

    path = write_config(tmp_path, config_data, "nested_override.yml")

    manager = ConfigurationManager(path)
    config = manager.get_sensor_config("sensor.partial")

    assert config.validation.range.min == -10
    assert config.validation.range.max == 50
    assert config.validation.roc.max_per_minute == 1.5


def test_strategy_objects_are_cached_for_normalization_imputation_smoothing(
    tmp_path, config_manager_defaults
) -> None:
    """ConfigurationManager caches normalization, imputation, and smoothing strategies."""
    config_data = config_manager_defaults
    config_data["sensors"] = {
        "sensor.standard": {
            "units": "C",
            "normalization": {"strategy": "min_max", "input_max": 10.0},
            "imputation": {"strategy": "forward_fill_with_decay", "decay_seconds": 30},
            "smoothing": {"strategy": "ewma", "alpha": 0.2},
            "calibration": {"strategy": "affine", "offset": 2.5},
        }
    }

    path = write_config(tmp_path, config_data, "strategy_cache.yml")

    manager = ConfigurationManager(path)

    normalization_first = manager.get_normalization_strategy("sensor.standard")
    normalization_second = manager.get_normalization_strategy("sensor.standard")
    assert normalization_first is normalization_second
    assert isinstance(normalization_first, MinMaxNormalization)

    imputation_first = manager.get_imputation_strategy("sensor.standard")
    imputation_second = manager.get_imputation_strategy("sensor.standard")
    assert imputation_first is imputation_second
    assert isinstance(imputation_first, ForwardFillWithDecay)

    smoothing_first = manager.get_smoothing_strategy("sensor.standard")
    smoothing_second = manager.get_smoothing_strategy("sensor.standard")
    assert smoothing_first is smoothing_second
    assert isinstance(smoothing_first, EWMASmoothing)

    calibration_first = manager.get_calibration_strategy("sensor.standard")
    calibration_second = manager.get_calibration_strategy("sensor.standard")
    assert calibration_first is calibration_second
    assert isinstance(calibration_first, ExecutableAffine)


def test_strategy_defaults_when_sections_missing(
    tmp_path, config_manager_defaults
) -> None:
    """Missing strategy sections should fall back to defaults."""
    config_data = config_manager_defaults
    config_data["sensors"] = {"sensor.standard": {"units": "C"}}

    path = write_config(tmp_path, config_data, "defaults.yml")

    manager = ConfigurationManager(path)

    calibration = manager.get_calibration_strategy("sensor.standard")
    normalization = manager.get_normalization_strategy("sensor.standard")
    imputation = manager.get_imputation_strategy("sensor.standard")
    smoothing = manager.get_smoothing_strategy("sensor.standard")

    assert isinstance(calibration, ExecutableIdentityCalibration)
    assert isinstance(normalization, IdentityNormalization)
    assert isinstance(imputation, ForwardFillWithDecay)
    assert isinstance(smoothing, PassThroughSmoothing)


def test_template_override_preserves_strategy_fields(
    tmp_path, config_manager_defaults
) -> None:
    """Strategy overrides should preserve template fields when partial."""
    config_data = config_manager_defaults
    config_data["templates"] = {
        "temp_sensor": {
            "units": "C",
            "calibration": {"strategy": "affine", "scale": 1.0, "offset": 0.5},
            "normalization": {
                "strategy": "min_max",
                "input_min": 0.0,
                "input_max": 10.0,
            },
        }
    }
    config_data["sensors"] = {
        "sensor.partial": {
            "template": "temp_sensor",
            "calibration": {"strategy": "affine", "scale": 2.0},
            "normalization": {"strategy": "min_max", "output_max": 5.0},
        }
    }

    path = write_config(tmp_path, config_data, "strategy_override.yml")

    manager = ConfigurationManager(path)
    config = manager.get_sensor_config("sensor.partial")

    assert config.calibration.scale == 2.0
    assert config.calibration.offset == 0.5
    assert config.normalization.output_max == 5.0
    assert config.normalization.input_max == 10.0


def test_profile_ids_track_mixed_overrides(tmp_path, config_manager_defaults) -> None:
    """Profile IDs should reflect only overridden sections."""
    config_data = config_manager_defaults
    config_data["templates"] = {
        "temp_sensor": {
            "units": "C",
            "calibration": {"strategy": "affine", "scale": 1.0, "offset": 0.0},
            "normalization": {"strategy": "min_max", "input_max": 10.0},
        }
    }
    config_data["sensors"] = {
        "sensor.mixed": {
            "template": "temp_sensor",
            "calibration": {"strategy": "affine", "offset": 2.5},
        }
    }

    path = write_config(tmp_path, config_data, "profile_ids.yml")

    manager = ConfigurationManager(path)
    config = manager.get_sensor_config("sensor.mixed")

    assert config.calibration_profile_id == "temp_sensor:sensor.mixed-custom"
    assert config.normalization_profile_id == "temp_sensor"


def test_empty_strategy_block_rejected(tmp_path, config_manager_defaults) -> None:
    """Empty strategy mappings should fail validation."""
    config_data = config_manager_defaults
    config_data["sensors"] = {"sensor.empty": {"units": "C", "imputation": {}}}

    path = write_config(tmp_path, config_data, "empty_strategy.yml")

    with pytest.raises(ClassValidationError):
        ConfigurationManager(path)


def test_malformed_system_windows_rejected(tmp_path, config_manager_defaults) -> None:
    """Invalid window types should raise schema validation errors."""
    config_data = config_manager_defaults
    config_data["system"]["windows"]["small_sec"] = "fast"
    config_data["sensors"] = {"sensor.standard": {"units": "C"}}

    path = write_config(tmp_path, config_data, "bad_windows.yml")

    with pytest.raises(ClassValidationError):
        ConfigurationManager(path)


def test_malformed_system_weights_rejected(tmp_path, config_manager_defaults) -> None:
    """Invalid weight types should raise schema validation errors."""
    config_data = config_manager_defaults
    config_data["system"]["weights"]["range_ok"] = "high"
    config_data["sensors"] = {"sensor.standard": {"units": "C"}}

    path = write_config(tmp_path, config_data, "bad_weights.yml")

    with pytest.raises(ClassValidationError):
        ConfigurationManager(path)
