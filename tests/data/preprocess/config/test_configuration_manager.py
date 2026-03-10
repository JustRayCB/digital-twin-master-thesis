import copy

import pytest
import yaml
from cattrs.errors import ClassValidationError

from dt.communication.topics import Topics
from dt.data.preprocess.config.manager import ConfigurationManager
from dt.data.preprocess.config.types import (AffineCalibrationConfig,
                                             MinMaxNormalizationConfig)
from dt.data.preprocess.stages.calibration import \
    AffineCalibration as ExecutableAffine
from dt.data.preprocess.stages.calibration import \
    IdentityCalibration as ExecutableIdentityCalibration
from dt.data.preprocess.stages.imputation import ForwardFillWithDecay
from dt.data.preprocess.stages.normalization import (IdentityNormalization,
                                                     MinMaxNormalization)
from dt.data.preprocess.stages.smoothing import (EWMASmoothing,
                                                 PassThroughSmoothing)


def write_config(tmp_path, config_data: dict[str, object], filename: str) -> str:
    """Write a config dictionary to a named temp file and return the path."""
    config_path = tmp_path / filename
    config_path.write_text(yaml.safe_dump(config_data))
    return str(config_path)


def write_default_config_file(tmp_path, config_manager_defaults) -> str:
    """Write the shared configuration-manager test config and return the path."""
    config_data = copy.deepcopy(config_manager_defaults)
    config_data["templates"] = {
        "temp_sensor": {
            "units": "C",
            "calibration": {"strategy": "affine", "scale": 1.0, "offset": 0.0},
            "validation": {"range": {"min": -10, "max": 50}},
        }
    }
    config_data["streams"] = [
        {
            "sensor": "sensor.standard",
            "topic": "temperature",
            "template": "temp_sensor",
        },
        {
            "sensor": "sensor.calibrated",
            "topic": "temperature",
            "template": "temp_sensor",
            "calibration": {"strategy": "affine", "offset": 2.5},
        },
        {
            "sensor": "sensor.custom",
            "topic": "temperature",
            "units": "V",
            "normalization": {"strategy": "min_max", "input_max": 10.0},
        },
    ]

    return write_config(tmp_path, config_data, "test_config.yml")


def test_stream_inherits_from_template(tmp_path, config_manager_defaults) -> None:
    """A stream inherits defaults from its referenced template."""
    manager = ConfigurationManager(write_default_config_file(tmp_path, config_manager_defaults))
    config = manager.get_stream_config("sensor.standard", Topics.TEMPERATURE)

    assert config.units == "C"
    assert isinstance(config.calibration, AffineCalibrationConfig)
    assert config.calibration.scale == 1.0
    assert config.calibration.offset == 0.0
    assert config.validation.range.min == -10


def test_stream_override_merges_with_template(tmp_path, config_manager_defaults) -> None:
    """Per-stream overrides should replace template fields."""
    manager = ConfigurationManager(write_default_config_file(tmp_path, config_manager_defaults))
    config = manager.get_stream_config("sensor.calibrated", Topics.TEMPERATURE)

    assert config.units == "C"
    assert config.calibration.scale == 1.0
    assert config.calibration.offset == 2.5


def test_stream_without_template_loads_standalone_config(tmp_path, config_manager_defaults) -> None:
    """Standalone streams can define strategy blocks without templates."""
    manager = ConfigurationManager(write_default_config_file(tmp_path, config_manager_defaults))
    config = manager.get_stream_config("sensor.custom", Topics.TEMPERATURE)

    assert config.units == "V"
    assert isinstance(config.normalization, MinMaxNormalizationConfig)
    assert config.normalization.input_max == 10.0


def test_stream_config_objects_are_cached(tmp_path, config_manager_defaults) -> None:
    """ConfigurationManager caches loaded stream configs."""
    manager = ConfigurationManager(write_default_config_file(tmp_path, config_manager_defaults))
    first = manager.get_stream_config("sensor.standard", Topics.TEMPERATURE)
    second = manager.get_stream_config("sensor.standard", Topics.TEMPERATURE)
    assert first is second


def test_unknown_stream_raises_key_error(tmp_path, config_manager_defaults) -> None:
    """Unknown stream bindings raise KeyError."""
    manager = ConfigurationManager(write_default_config_file(tmp_path, config_manager_defaults))
    with pytest.raises(KeyError):
        manager.get_stream_config("sensor.ghost", Topics.TEMPERATURE)


def test_unknown_template_raises_error(tmp_path, config_manager_defaults) -> None:
    """Unknown templates referenced by streams raise ValueError."""
    config_data = copy.deepcopy(config_manager_defaults)
    config_data["streams"] = [{"sensor": "broken", "topic": "temperature", "template": "missing"}]
    path = write_config(tmp_path, config_data, "broken.yml")

    manager = ConfigurationManager(path)
    with pytest.raises(ValueError, match="unknown template"):
        manager.get_stream_config("broken", Topics.TEMPERATURE)


def test_profile_ids_reflect_overrides(tmp_path, config_manager_defaults) -> None:
    """Profile IDs encode which stream blocks were overridden."""
    manager = ConfigurationManager(write_default_config_file(tmp_path, config_manager_defaults))

    standard = manager.get_stream_config("sensor.standard", Topics.TEMPERATURE)
    assert standard.calibration_profile_id == "temp_sensor"
    assert standard.normalization_profile_id == "temp_sensor"

    calibrated = manager.get_stream_config("sensor.calibrated", Topics.TEMPERATURE)
    assert calibrated.calibration_profile_id == "temp_sensor:sensor.calibrated-custom"
    assert calibrated.normalization_profile_id == "temp_sensor"

    custom = manager.get_stream_config("sensor.custom", Topics.TEMPERATURE)
    assert custom.normalization_profile_id == "standalone:sensor.custom"
    assert custom.calibration_profile_id == "default"


def test_resolve_sensor_config_maps_db_id_to_stream_key(
    tmp_path,
    config_manager_defaults,
    sensor_registry,
    configure_preprocess_db_client,
) -> None:
    """resolve_sensor_config maps DB sensor IDs back to configured streams."""
    sensor = sensor_registry["register"]("sensor.standard")

    manager = ConfigurationManager(write_default_config_file(tmp_path, config_manager_defaults))
    stream_key, stream_config = manager.resolve_sensor_config(
        plant_id=sensor.plant_id,
        sensor_id=sensor.id,
        topic=Topics.TEMPERATURE,
    )

    assert stream_key == "sensor.standard"
    assert stream_config.units == "C"


def test_resolve_sensor_config_distinguishes_same_topic_for_two_sensors(
    tmp_path,
    config_manager_defaults,
    sensor_registry,
    configure_preprocess_db_client,
) -> None:
    """Two sensors on the same topic can resolve different configs."""
    config_data = copy.deepcopy(config_manager_defaults)
    config_data["templates"] = {
        "dht22.temperature": {"units": "C", "validation": {"range": {"min": -10, "max": 50}}},
        "ds18b20.temperature": {
            "units": "C",
            "validation": {"range": {"min": -20, "max": 100}},
        },
    }
    config_data["streams"] = [
        {
            "sensor": "sensors.basil.dht22.001.temperature",
            "topic": "temperature",
            "template": "dht22.temperature",
        },
        {
            "sensor": "sensors.basil.ds18b20.001.temperature",
            "topic": "temperature",
            "template": "ds18b20.temperature",
        },
    ]
    path = write_config(tmp_path, config_data, "two_temperature_sensors.yml")

    dht22 = sensor_registry["register"]("sensors.basil.dht22.001.temperature")
    ds18b20 = sensor_registry["register"]("sensors.basil.ds18b20.001.temperature")

    manager = ConfigurationManager(path)
    _, dht22_config = manager.resolve_sensor_config(dht22.plant_id, dht22.id, Topics.TEMPERATURE)
    _, ds18b20_config = manager.resolve_sensor_config(
        ds18b20.plant_id, ds18b20.id, Topics.TEMPERATURE
    )

    assert dht22_config.validation.range.max == 50
    assert ds18b20_config.validation.range.max == 100


def test_resolve_sensor_config_distinguishes_multiple_topics_for_one_sensor_id(
    tmp_path,
    config_manager_defaults,
    sensor_registry,
    configure_preprocess_db_client,
) -> None:
    """The same sensor ID can resolve different configs for different topics."""
    config_data = copy.deepcopy(config_manager_defaults)
    config_data["templates"] = {
        "camera.snapshot": {
            "units": "image/jpeg",
            "validation": {"range": {"min": 0.0, "max": 1_000_000.0}},
        },
        "camera.green_ratio": {
            "units": "ratio",
            "validation": {"range": {"min": 0.0, "max": 1.0}},
        },
    }
    config_data["streams"] = [
        {
            "sensor": "sensors.basil.picamera2.001.camera_image",
            "topic": "camera_image",
            "template": "camera.snapshot",
        },
        {
            "sensor": "sensors.basil.picamera2.001.camera_image",
            "topic": "green_ratio",
            "template": "camera.green_ratio",
        },
    ]
    path = write_config(tmp_path, config_data, "camera_multi_stream.yml")

    sensor = sensor_registry["register"]("sensors.basil.picamera2.001.camera_image")

    manager = ConfigurationManager(path)
    snapshot_key, snapshot_config = manager.resolve_sensor_config(
        sensor.plant_id, sensor.id, Topics.CAMERA_IMAGE
    )
    ratio_key, ratio_config = manager.resolve_sensor_config(
        sensor.plant_id, sensor.id, Topics.GREEN_RATIO
    )

    assert snapshot_key == "sensors.basil.picamera2.001.camera_image"
    assert snapshot_config.units == "image/jpeg"
    assert ratio_key == "sensors.basil.picamera2.001.camera_image"
    assert ratio_config.units == "ratio"


def test_profile_ids_distinguish_multiple_topics_for_one_sensor_name(
    tmp_path, config_manager_defaults
) -> None:
    """Traceability IDs should stay distinct when one sensor name emits multiple topics."""
    config_data = copy.deepcopy(config_manager_defaults)
    config_data["streams"] = [
        {
            "sensor": "sensors.basil.picamera2.001.camera_image",
            "topic": "camera_image",
            "units": "image/jpeg",
            "calibration": {"strategy": "identity"},
        },
        {
            "sensor": "sensors.basil.picamera2.001.camera_image",
            "topic": "green_ratio",
            "units": "ratio",
            "calibration": {"strategy": "identity"},
        },
    ]
    path = write_config(tmp_path, config_data, "camera_profile_ids.yml")

    manager = ConfigurationManager(path)
    snapshot_config = manager.get_stream_config(
        "sensors.basil.picamera2.001.camera_image", Topics.CAMERA_IMAGE
    )
    ratio_config = manager.get_stream_config(
        "sensors.basil.picamera2.001.camera_image", Topics.GREEN_RATIO
    )

    assert snapshot_config.calibration_profile_id == (
        "standalone:sensors.basil.picamera2.001.camera_image:camera_image"
    )
    assert ratio_config.calibration_profile_id == (
        "standalone:sensors.basil.picamera2.001.camera_image:green_ratio"
    )


def test_resolve_sensor_config_rejects_missing_derived_stream_config(
    tmp_path,
    config_manager_defaults,
    sensor_registry,
    configure_preprocess_db_client,
) -> None:
    """A derived stream must not fall back to another stream config."""
    config_data = copy.deepcopy(config_manager_defaults)
    config_data["templates"] = {
        "camera.snapshot": {
            "units": "image/jpeg",
            "validation": {"range": {"min": 0.0, "max": 1_000_000.0}},
        }
    }
    config_data["streams"] = [
        {
            "sensor": "sensors.basil.picamera2.001.camera_image",
            "topic": "camera_image",
            "template": "camera.snapshot",
        }
    ]
    path = write_config(tmp_path, config_data, "camera_missing_derived.yml")

    sensor = sensor_registry["register"]("sensors.basil.picamera2.001.camera_image")

    manager = ConfigurationManager(path)
    with pytest.raises(KeyError):
        manager.resolve_sensor_config(sensor.plant_id, sensor.id, Topics.GREEN_RATIO)


def test_duplicate_stream_binding_rejected(tmp_path, config_manager_defaults) -> None:
    """Duplicate `(sensor, topic)` bindings should fail fast."""
    config_data = copy.deepcopy(config_manager_defaults)
    config_data["streams"] = [
        {"sensor": "sensor.standard", "topic": "temperature", "units": "C"},
        {"sensor": "sensor.standard", "topic": "temperature", "units": "C"},
    ]
    path = write_config(tmp_path, config_data, "duplicate_streams.yml")

    with pytest.raises(ValueError, match="Duplicate stream binding"):
        ConfigurationManager(path)


def test_db_registry_failures_do_not_block_local_config_access(
    tmp_path, config_manager_defaults, monkeypatch
) -> None:
    """Local config access should still work when the runtime sensor registry cannot load."""
    path = write_default_config_file(tmp_path, config_manager_defaults)

    class BrokenDatabaseClient:
        def list_sensors(self):
            raise RuntimeError("database offline")

    import dt.data.preprocess.config.manager as preprocess_config_manager

    monkeypatch.setattr(preprocess_config_manager, "DatabaseApiClient", BrokenDatabaseClient)

    manager = ConfigurationManager(path)

    config = manager.get_stream_config("sensor.standard", Topics.TEMPERATURE)
    assert config.units == "C"

    with pytest.raises(KeyError, match="No sensor stream registry entry"):
        manager.resolve_sensor_config(plant_id=1, sensor_id=1, topic=Topics.TEMPERATURE)


def test_template_override_preserves_nested_fields(tmp_path, config_manager_defaults) -> None:
    """Nested overrides should preserve template values when fields are omitted."""
    config_data = copy.deepcopy(config_manager_defaults)
    config_data["templates"] = {
        "temp_sensor": {
            "units": "C",
            "validation": {"range": {"min": -10, "max": 50}},
        }
    }
    config_data["streams"] = [
        {
            "sensor": "sensor.partial",
            "topic": "temperature",
            "template": "temp_sensor",
            "validation": {"roc": {"max_per_minute": 1.5}},
        }
    ]
    path = write_config(tmp_path, config_data, "nested_override.yml")

    manager = ConfigurationManager(path)
    config = manager.get_stream_config("sensor.partial", Topics.TEMPERATURE)

    assert config.validation.range.min == -10
    assert config.validation.range.max == 50
    assert config.validation.roc.max_per_minute == 1.5


def test_strategy_objects_are_cached_for_normalization_imputation_smoothing(
    tmp_path, config_manager_defaults
) -> None:
    """ConfigurationManager caches strategy instances per stream."""
    config_data = copy.deepcopy(config_manager_defaults)
    config_data["streams"] = [
        {
            "sensor": "sensor.standard",
            "topic": "temperature",
            "units": "C",
            "normalization": {"strategy": "min_max", "input_max": 10.0},
            "imputation": {"strategy": "forward_fill_with_decay", "decay_seconds": 30},
            "smoothing": {"strategy": "ewma", "alpha": 0.2},
            "calibration": {"strategy": "affine", "offset": 2.5},
        }
    ]
    path = write_config(tmp_path, config_data, "strategy_cache.yml")

    manager = ConfigurationManager(path)
    normalization_first = manager.get_normalization_strategy("sensor.standard", Topics.TEMPERATURE)
    normalization_second = manager.get_normalization_strategy("sensor.standard", Topics.TEMPERATURE)
    assert normalization_first is normalization_second
    assert isinstance(normalization_first, MinMaxNormalization)

    imputation_first = manager.get_imputation_strategy("sensor.standard", Topics.TEMPERATURE)
    imputation_second = manager.get_imputation_strategy("sensor.standard", Topics.TEMPERATURE)
    assert imputation_first is imputation_second
    assert isinstance(imputation_first, ForwardFillWithDecay)

    smoothing_first = manager.get_smoothing_strategy("sensor.standard", Topics.TEMPERATURE)
    smoothing_second = manager.get_smoothing_strategy("sensor.standard", Topics.TEMPERATURE)
    assert smoothing_first is smoothing_second
    assert isinstance(smoothing_first, EWMASmoothing)

    calibration_first = manager.get_calibration_strategy("sensor.standard", Topics.TEMPERATURE)
    calibration_second = manager.get_calibration_strategy("sensor.standard", Topics.TEMPERATURE)
    assert calibration_first is calibration_second
    assert isinstance(calibration_first, ExecutableAffine)


def test_strategy_defaults_when_sections_missing(tmp_path, config_manager_defaults) -> None:
    """Missing strategy sections should fall back to defaults."""
    config_data = copy.deepcopy(config_manager_defaults)
    config_data["streams"] = [{"sensor": "sensor.standard", "topic": "temperature", "units": "C"}]
    path = write_config(tmp_path, config_data, "defaults.yml")

    manager = ConfigurationManager(path)
    calibration = manager.get_calibration_strategy("sensor.standard", Topics.TEMPERATURE)
    normalization = manager.get_normalization_strategy("sensor.standard", Topics.TEMPERATURE)
    imputation = manager.get_imputation_strategy("sensor.standard", Topics.TEMPERATURE)
    smoothing = manager.get_smoothing_strategy("sensor.standard", Topics.TEMPERATURE)

    assert isinstance(calibration, ExecutableIdentityCalibration)
    assert isinstance(normalization, IdentityNormalization)
    assert isinstance(imputation, ForwardFillWithDecay)
    assert isinstance(smoothing, PassThroughSmoothing)


def test_template_override_preserves_strategy_fields(tmp_path, config_manager_defaults) -> None:
    """Strategy overrides should preserve template fields when partial."""
    config_data = copy.deepcopy(config_manager_defaults)
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
    config_data["streams"] = [
        {
            "sensor": "sensor.partial",
            "topic": "temperature",
            "template": "temp_sensor",
            "calibration": {"strategy": "affine", "scale": 2.0},
            "normalization": {"strategy": "min_max", "output_max": 5.0},
        }
    ]
    path = write_config(tmp_path, config_data, "strategy_override.yml")

    manager = ConfigurationManager(path)
    config = manager.get_stream_config("sensor.partial", Topics.TEMPERATURE)

    assert config.calibration.scale == 2.0
    assert config.calibration.offset == 0.5
    assert config.normalization.output_max == 5.0
    assert config.normalization.input_max == 10.0


def test_empty_strategy_block_rejected(tmp_path, config_manager_defaults) -> None:
    """Empty strategy mappings should fail validation."""
    config_data = copy.deepcopy(config_manager_defaults)
    config_data["streams"] = [
        {"sensor": "sensor.empty", "topic": "temperature", "units": "C", "imputation": {}}
    ]
    path = write_config(tmp_path, config_data, "empty_strategy.yml")

    with pytest.raises(ClassValidationError):
        ConfigurationManager(path)


def test_malformed_system_windows_rejected(tmp_path, config_manager_defaults) -> None:
    """Invalid window types should raise schema validation errors."""
    config_data = copy.deepcopy(config_manager_defaults)
    config_data["system"]["windows"]["small_sec"] = "fast"
    config_data["streams"] = [{"sensor": "sensor.standard", "topic": "temperature", "units": "C"}]
    path = write_config(tmp_path, config_data, "bad_windows.yml")

    with pytest.raises(ClassValidationError):
        ConfigurationManager(path)


def test_malformed_system_weights_rejected(tmp_path, config_manager_defaults) -> None:
    """Invalid weight types should raise schema validation errors."""
    config_data = copy.deepcopy(config_manager_defaults)
    config_data["system"]["weights"]["range_ok"] = "high"
    config_data["streams"] = [{"sensor": "sensor.standard", "topic": "temperature", "units": "C"}]
    path = write_config(tmp_path, config_data, "bad_weights.yml")

    with pytest.raises(ClassValidationError):
        ConfigurationManager(path)
