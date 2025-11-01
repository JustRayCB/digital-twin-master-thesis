from unittest.mock import Mock

import pytest

from dt.data.preprocess.configuration.preprocessing_config import \
    SensorValidationConfig
from dt.communication.topics import Topics
from dt.data.preprocess.configuration.manager import ConfigurationManager


def test_configuration_manager_loads_config(test_config_path):
    """Test that ConfigurationManager loads the YAML config."""
    manager = ConfigurationManager(test_config_path)
    validation_config = SensorValidationConfig.load(test_config_path)

    assert manager.rules is not None
    assert manager.rules == validation_config
    assert "dht22.temperature" in manager.rules.sensors
    assert "bh1750.lux" in manager.rules.sensors


def test_resolve_sensor_config_by_registry(test_config_path, mock_db_client):
    """Test resolving sensor config using the database registry."""
    # Mock DB to return a known sensor
    sensor_descriptor = Mock()
    sensor_descriptor.sensor_id = 101
    sensor_descriptor.name = "dht22.temperature"
    mock_db_client.return_value.list_sensors.return_value = [sensor_descriptor]

    manager = ConfigurationManager(test_config_path)

    sensor_key, sensor_config = manager.resolve_sensor_config(
        plant_id=1,
        sensor_id=101,
        topic=Topics.TEMPERATURE,
    )

    assert sensor_key == "dht22.temperature"
    assert sensor_config.range.min == -40
    assert sensor_config.range.max == 80


def test_resolve_sensor_config_unknown_sensor(test_config_path, mock_db_client):
    """Test that unknown sensors raise KeyError."""
    manager = ConfigurationManager(test_config_path)

    with pytest.raises(KeyError, match="No sensor registry entry"):
        manager.resolve_sensor_config(
            plant_id=1,
            sensor_id=999,  # Unknown
            topic=Topics.TEMPERATURE,
        )


def test_get_calibration_strategy_cached(test_config_path):
    """Test that calibration strategies are cached."""
    manager = ConfigurationManager(test_config_path)

    strategy1, profile1 = manager.get_calibration_strategy("dht22.temperature", 101)
    strategy2, profile2 = manager.get_calibration_strategy("dht22.temperature", 101)

    # Should return the same cached instance
    assert strategy1 is strategy2
    assert profile1 is profile2


def test_get_imputation_strategy_cached(test_config_path):
    """Test that imputation strategies are cached."""
    manager = ConfigurationManager(test_config_path)
    sensor_config = manager.rules.sensors["dht22.temperature"]

    strategy1 = manager.get_imputation_strategy("dht22.temperature", sensor_config)
    strategy2 = manager.get_imputation_strategy("dht22.temperature", sensor_config)

    assert strategy1 is strategy2


def test_get_dq_weights(test_config_path):
    """Test retrieving data quality weights."""
    manager = ConfigurationManager(test_config_path)

    weights = manager.get_dq_weights()

    assert weights["range_ok"] == 0.4
    assert weights["roc_ok"] == 0.3
    assert weights["stuck_ok"] == 0.3
