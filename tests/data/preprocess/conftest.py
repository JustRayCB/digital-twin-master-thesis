import threading
import time
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.db_client import DatabaseApiClient
from dt.communication.dataclasses import SensorDescriptor
from dt.communication.topics import Topics
from dt.data.database.app import create_app
from dt.data.database.migrations.runner import MigrationRunner
from dt.data.database.timescale_storage import TimescaleStorage
from dt.data.preprocess.core.state import StateProvider
from dt.utils import Config


@pytest.fixture
def test_config_path(tmp_path: Path) -> str:
    """Create a temporary preprocessing configuration file for tests (New Unified Schema)."""
    config_content = """
system:
  windows:
    small_sec: 60
    medium_sec: 300
    big_sec: 1000
  weights:
    range_ok: 0.4
    roc_ok: 0.3
    stuck_ok: 0.3

templates:
  dht22.temperature:
    units: "°C"
    validation:
      range: { min: -40, max: 80 }
      roc: { max_per_minute: 5.0 }
      stuck: { max_flat_seconds: 300 }
    imputation:
      strategy: forward_fill_with_decay
      max_gap_seconds: 600
      decay_seconds: 300
      baseline: null
    calibration:
      strategy: affine
      scale: 1.05
      offset: -0.5
    normalization:
      strategy: min_max
      input_min: -40
      input_max: 80
      output_min: 0.0
      output_max: 1.0
      clip: true
    smoothing:
      strategy: pass_through

  bh1750.lux:
    units: "lux"
    validation:
      range: { min: 1, max: 65535 }
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
    calibration:
      strategy: identity
    normalization:
      strategy: min_max
      input_min: 0.0
      input_max: 65535.0
      output_min: 0.0
      output_max: 1.0
      clip: true

sensors:
  # Map generic types to templates
  dht22.temperature: { template: dht22.temperature }
  bh1750.lux: { template: bh1750.lux }

  # Overrides
  sensors.greenhouse.dht22.001.temperature:
    template: dht22.temperature
    calibration:
      strategy: affine
      offset: -0.2

  sensors.greenhouse.bh1750.001:
    template: bh1750.lux
    normalization:
      strategy: min_max
      input_max: 20000.0
"""
    config_file = tmp_path / "preprocessing_config.yml"
    config_file.write_text(config_content)
    return str(config_file)


@pytest.fixture
def mock_db_client():
    """Mock the DatabaseApiClient to avoid external dependencies."""
    with patch("dt.data.preprocess.config.manager.DatabaseApiClient") as mock:
        mock.return_value.list_sensors.return_value = []
        yield mock


@pytest.fixture
def mock_state_provider():
    """Create a mock state provider."""
    return Mock(spec=StateProvider)


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
def base_config() -> dict[str, object]:
    """Reusable preprocessing configuration for stream integration tests."""
    return {
        "system": {
            "windows": {"small_sec": 60, "medium_sec": 300, "big_sec": 600},
            "weights": {"range_ok": 0.5, "roc_ok": 0.3, "stuck_ok": 0.2},
        },
        "templates": {
            "greenhouse.temperature.defaults": {
                "units": "C",
                "validation": {
                    "range": {"min": 10.0, "max": 30.0},
                    "roc": {"max_per_minute": 2.5},
                    "stuck": {"max_flat_seconds": 120},
                },
                "imputation": {
                    "strategy": "forward_fill_with_decay",
                    "max_gap_seconds": 300,
                    "decay_seconds": 120,
                    "baseline": None,
                },
                "calibration": {"strategy": "identity"},
                "normalization": {"strategy": "identity"},
                "smoothing": {"strategy": "pass_through"},
            }
        },
        "sensors": {"greenhouse.temperature": {"template": "greenhouse.temperature.defaults"}},
    }


@pytest.fixture(scope="module")
def spark_session():
    """Provide a Spark session configured for local streaming tests."""
    try:
        from pyspark.sql import SparkSession

        session = (
            SparkSession.builder.master("local[*]")  # pyright: ignore[]
            .appName("preprocessing-tests")
            .config("spark.driver.host", "127.0.0.1")
            .config("spark.driver.bindAddress", "127.0.0.1")
            .getOrCreate()
        )
    except Exception as exc:
        pytest.skip(f"Spark session could not start in this environment: {exc}")

    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


@pytest.fixture(scope="module")
def postgres_container(spark_session):
    """Start a PostgreSQL container with TimescaleDB extension."""
    try:
        from testcontainers.postgres import PostgresContainer

        with PostgresContainer(image="timescale/timescaledb:latest-pg18", driver="psycopg") as postgres:
            time.sleep(2)
            yield postgres
    except Exception as exc:
        pytest.skip(f"Timescale test container could not start in this environment: {exc}")


@pytest.fixture(scope="module")
def db_engine(postgres_container):
    """Create SQLAlchemy engine and run migrations for the test database."""
    from sqlalchemy import create_engine

    db_url = postgres_container.get_connection_url()
    engine = create_engine(db_url, pool_pre_ping=True)

    psycopg_url = db_url.replace("postgresql+psycopg://", "postgresql://")
    runner = MigrationRunner(migrations_dir=Config.DB_MIGRATIONS_DIR, db_url=psycopg_url)
    runner.run_migrations()

    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def timescale_storage(db_engine):
    """Timescale storage connected to the test database."""
    return TimescaleStorage(engine=db_engine)


@pytest.fixture(scope="module")
def database_service_url(spark_session, timescale_storage):
    """Run the Flask database service backed by the Timescale test container."""
    from werkzeug.serving import make_server

    app = create_app(config=type("TestConfig", (), {}), storage=timescale_storage)
    server = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.fixture
def sensor_registry(timescale_storage):
    """Helper to register sensors in the Timescale test database."""
    plant_id = timescale_storage.upsert_plant(name="Test Plant (preprocess)")

    def register(name: str, read_interval: int = 60) -> SensorDescriptor:
        sensor = SensorDescriptor(
            id=-1,
            plant_id=plant_id,
            name=name,
            pin=0,
            read_interval=read_interval,
        )
        sensor_id = timescale_storage.register_sensor(sensor)
        sensor.id = sensor_id
        return sensor

    return {"plant_id": plant_id, "register": register}


@pytest.fixture
def configure_preprocess_db_client(monkeypatch, database_service_url):
    """Route preprocessing ConfigurationManager DB lookups to the test database service."""
    import dt.data.preprocess.config.manager as preprocess_config_manager

    monkeypatch.setattr(
        preprocess_config_manager,
        "DatabaseApiClient",
        partial(DatabaseApiClient, base_url=database_service_url),
    )
    return database_service_url
