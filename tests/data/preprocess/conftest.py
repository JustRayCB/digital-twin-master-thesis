from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pyspark.sql import SparkSession

from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics
from dt.data.preprocess.configuration.profiles import (ProfileDefinition,
                                                          ProfileParameters)
from dt.data.preprocess.state import StateProvider


@pytest.fixture
def test_config_path(tmp_path: Path) -> str:
    """Create a temporary preprocessing configuration file for tests."""
    config_content = """
defaults:
  windows:
    small_sec: 60
    medium_sec: 300
    big_sec: 1000
  scoring:
    weights:
      range_ok: 0.4
      roc_ok: 0.3
      stuck_ok: 0.3

sensors:
  dht22.temperature:
    units: "°C"
    range:
      min: -40
      max: 80
    accuracy: 0.5
    roc:
      max_per_minute: 5.0
    stuck:
      max_flat_seconds: 300
    imputation:
      strategy: forward_fill_with_decay
      max_gap_seconds: 600
      decay_seconds: 300
      baseline: null
    smoothing:
      strategy: pass_through
  bh1750.lux:
    units: "lux"
    range: { min: 1, max: 65535 }
    accuracy: 13107
    roc:
      profiles: 
        indoor:  { max_per_minute: 100 }
        outdoor: { max_per_minute: 1000 }
      active_profile: indoor
    stuck: { max_flat_seconds: 180 } 
    imputation:
      strategy: window_average
      window_seconds: 180
      min_samples: 3
      max_gap_seconds: 240
      decay_seconds: 0

calibration_profiles:
  defaults:
    dht22.temperature:
      profile_id: calibration.dht22.temperature.test
      strategy: affine
      parameters:
        scale: 1.05
        offset: -0.5
  overrides:
    sensors.greenhouse.dht22.001.temperature:
      sensor_type: dht22.temperature
      profile_id: calibration.dht22.temperature.greenhouse-001
      parameters:
        offset: -0.2

normalization_profiles:
  defaults:
    dht22.temperature:
      profile_id: normalization.dht22.temperature.test
      strategy: min_max
      parameters:
        input_min: -40
        input_max: 80
        output_min: 0.0
        output_max: 1.0
        clip: true
    bh1750.lux:
      profile_id: normalization.bh1750.lux.test
      strategy: min_max
      parameters:
        input_min: 0.0
        input_max: 65535.0
        output_min: 0.0
        output_max: 1.0
        clip: true
  overrides:
    sensors.greenhouse.bh1750.001:
      sensor_type: bh1750.lux
      profile_id: normalization.bh1750.lux.greenhouse-001
      parameters:
        input_max: 20000.0

"""
    config_file = tmp_path / "preprocessing_config.yml"
    config_file.write_text(config_content)
    return str(config_file)


@pytest.fixture
def mock_db_client():
    """Mock the DatabaseApiClient to avoid external dependencies."""
    with patch("dt.data.preprocess.configuration.manager.DatabaseApiClient") as mock:
        mock.return_value.list_sensors.return_value = []
        yield mock


@pytest.fixture
def mock_state_provider():
    """Create a mock state provider."""
    return Mock(spec=StateProvider)


@pytest.fixture(scope="module")
def spark_session():
    """Provide a Spark session configured for local testing."""
    session = (
        SparkSession.builder.master("local[*]")  # pyright: ignore[]
        .appName("preprocessing-tests")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


@pytest.fixture
def sample_reading():
    """Create a sample raw sensor reading."""
    basetime = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return RawSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=basetime.timestamp(),
        value=25.5,
        unit="°C",
        topic=Topics.TEMPERATURE,
        correlation_id="test-correlation-id",
    )


@pytest.fixture
def preprocessing_config_path():
    """Path to the preprocessing configuration file."""
    return Path(__file__).resolve().parents[3] / "dt" / "utils" / "preprocessing_config.yml"


@pytest.fixture
def make_profile():
    def _inner(
        strategy: str,
        parameters: ProfileParameters | None,
        profile_id: str = "profile",
    ) -> ProfileDefinition:
        return ProfileDefinition(
            profile_id=profile_id,
            strategy=strategy,
            parameters=parameters,
        )

    return _inner
