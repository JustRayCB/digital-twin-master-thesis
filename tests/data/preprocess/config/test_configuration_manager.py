import pytest
import yaml

from dt.communication.dataclasses.sensor import SensorDescriptor
from dt.communication.topics import Topics
from dt.data.preprocess.config.manager import ConfigurationManager
from dt.data.preprocess.config.types import (
    AffineCalibrationConfig,
    IdentityCalibrationConfig,
    MinMaxNormalizationConfig,
)
from dt.data.preprocess.stages.calibration import AffineCalibration as ExecutableAffine


@pytest.fixture
def mock_config_file(tmp_path):
    config_data = {
        "system": {
            "windows": {"small_sec": 60, "medium_sec": 300, "big_sec": 1000},
            "weights": {"range_ok": 0.4, "roc_ok": 0.4, "stuck_ok": 0.2},
        },
        "templates": {
            "temp_sensor": {
                "units": "C",
                "calibration": {"strategy": "affine", "scale": 1.0, "offset": 0.0},
                "validation": {"range": {"min": -10, "max": 50}},
            }
        },
        "sensors": {
            "sensor.standard": {"template": "temp_sensor"},
            "sensor.calibrated": {
                "template": "temp_sensor",
                "calibration": {"strategy": "affine", "offset": 2.5},
            },
            "sensor.custom": {
                "units": "V",
                "normalization": {"strategy": "min_max", "input_max": 10.0},
            }
        },
    }

    path = tmp_path / "test_config.yml"
    path.write_text(yaml.safe_dump(config_data))
    return str(path)


def test_sensor_inherits_from_template(mock_config_file) -> None:
    """Sensor inherits defaults from its referenced template."""
    manager = ConfigurationManager(mock_config_file)
    config = manager.get_sensor_config("sensor.standard")

    assert config.units == "C"
    assert isinstance(config.calibration, AffineCalibrationConfig)
    assert config.calibration.scale == 1.0
    assert config.calibration.offset == 0.0
    assert config.validation.range.min == -10


def test_sensor_override_merges_with_template(mock_config_file) -> None:
    """Per-sensor overrides should replace template fields."""
    manager = ConfigurationManager(mock_config_file)
    config = manager.get_sensor_config("sensor.calibrated")

    assert config.units == "C"
    assert config.calibration.scale == 1.0
    assert config.calibration.offset == 2.5


def test_sensor_without_template_loads_standalone_config(mock_config_file) -> None:
    """Standalone sensors can define strategy blocks without templates."""
    manager = ConfigurationManager(mock_config_file)
    config = manager.get_sensor_config("sensor.custom")

    assert config.units == "V"
    assert isinstance(config.normalization, MinMaxNormalizationConfig)
    assert config.normalization.input_max == 10.0


def test_sensor_config_objects_are_cached(mock_config_file) -> None:
    """ConfigurationManager caches loaded SensorConfig objects."""
    manager = ConfigurationManager(mock_config_file)
    first = manager.get_sensor_config("sensor.standard")
    second = manager.get_sensor_config("sensor.standard")
    assert first is second


def test_strategy_objects_are_cached(mock_config_file) -> None:
    """ConfigurationManager caches built strategy objects."""
    manager = ConfigurationManager(mock_config_file)
    first = manager.get_calibration_strategy("sensor.standard")
    second = manager.get_calibration_strategy("sensor.standard")
    assert first is second
    assert isinstance(first, ExecutableAffine)


def test_unknown_sensor_raises_key_error(mock_config_file) -> None:
    """Unknown sensor keys raise KeyError."""
    manager = ConfigurationManager(mock_config_file)
    with pytest.raises(KeyError):
        manager.get_sensor_config("sensor.ghost")


def test_unknown_template_raises_error(tmp_path) -> None:
    """Unknown templates referenced by sensors raise ValueError."""
    data = {
        "system": {
            "windows": {"small_sec": 60, "medium_sec": 300, "big_sec": 1000},
            "weights": {"range_ok": 0.4, "roc_ok": 0.4, "stuck_ok": 0.2},
        },
        "sensors": {"broken": {"template": "missing"}},
    }
    path = tmp_path / "broken.yml"
    path.write_text(yaml.safe_dump(data))

    manager = ConfigurationManager(str(path))
    with pytest.raises(ValueError, match="unknown template"):
        manager.get_sensor_config("broken")


def test_profile_ids_reflect_overrides(mock_config_file) -> None:
    """Profile IDs encode which blocks were overridden."""
    manager = ConfigurationManager(mock_config_file)

    standard = manager.get_sensor_config("sensor.standard")
    assert standard.calibration_profile_id == "temp_sensor"
    assert standard.normalization_profile_id == "temp_sensor"

    calibrated = manager.get_sensor_config("sensor.calibrated")
    assert calibrated.calibration_profile_id == "temp_sensor:sensor.calibrated-custom"
    assert calibrated.normalization_profile_id == "temp_sensor"

    custom = manager.get_sensor_config("sensor.custom")
    assert custom.normalization_profile_id == "standalone:sensor.custom"
    assert custom.calibration_profile_id == "default"


def test_resolve_sensor_config_maps_db_id_to_config_key(mock_config_file, mock_db_client) -> None:
    """resolve_sensor_config maps DB sensor IDs back to configured sensor keys."""
    mock_db_client.return_value.list_sensors.return_value = [
        SensorDescriptor(id=42, plant_id=1, name="sensor.standard", pin=17, read_interval=5)
    ]

    manager = ConfigurationManager(mock_config_file)
    sensor_key, sensor_config = manager.resolve_sensor_config(
        plant_id=1, sensor_id=42, topic=Topics.TEMPERATURE
    )

    assert sensor_key == "sensor.standard"
    assert sensor_config.units == "C"


def test_resolve_sensor_config_falls_back_to_generic_key(tmp_path, mock_db_client) -> None:
    """resolve_sensor_config falls back to generic sensor keys when device keys missing."""
    config_data = {
        "system": {
            "windows": {"small_sec": 60, "medium_sec": 300, "big_sec": 1000},
            "weights": {"range_ok": 0.4, "roc_ok": 0.4, "stuck_ok": 0.2},
        },
        "templates": {"temp_sensor": {"units": "C", "validation": {"range": {"min": -10, "max": 50}}}},
        "sensors": {"dht22.temperature": {"template": "temp_sensor"}},
    }

    path = tmp_path / "generic_only.yml"
    path.write_text(yaml.safe_dump(config_data))

    mock_db_client.return_value.list_sensors.return_value = [
        SensorDescriptor(
            id=7,
            plant_id=1,
            name="sensors.basil.dht22.001.temperature",
            pin=17,
            read_interval=5,
        )
    ]

    manager = ConfigurationManager(str(path))
    sensor_key, sensor_config = manager.resolve_sensor_config(plant_id=1, sensor_id=7, topic=Topics.TEMPERATURE)

    assert sensor_key == "dht22.temperature"
    assert sensor_config.units == "C"


def test_resolve_sensor_config_rejects_numeric_yaml_keys(tmp_path, monkeypatch) -> None:
    """Numeric sensor keys in YAML are rejected to prevent ambiguous resolution."""
    config_data = {
        "system": {
            "windows": {"small_sec": 60, "medium_sec": 300, "big_sec": 1000},
            "weights": {"range_ok": 0.4, "roc_ok": 0.4, "stuck_ok": 0.2},
        },
        "sensors": {"7": {"units": "C"}},
    }

    path = tmp_path / "numeric_key.yml"
    path.write_text(yaml.safe_dump(config_data))

    def fake_list_sensors(self):
        return [
            SensorDescriptor(
                id=7,
                plant_id=1,
                name="sensors.basil.dht22.001.temperature",
                pin=17,
                read_interval=5,
            )
        ]

    monkeypatch.setattr("dt.communication.db_client.DatabaseApiClient.list_sensors", fake_list_sensors)

    manager = ConfigurationManager(str(path))
    with pytest.raises(KeyError):
        manager.resolve_sensor_config(plant_id=1, sensor_id=7, topic=Topics.TEMPERATURE)


def test_configuration_manager_supports_identity_calibration(test_config_path, mock_db_client) -> None:
    """ConfigurationManager returns identity calibration config when configured."""
    manager = ConfigurationManager(test_config_path)
    sensor_config = manager.get_sensor_config("bh1750.lux")
    assert isinstance(sensor_config.calibration, IdentityCalibrationConfig)
