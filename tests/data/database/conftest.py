"""Shared fixtures for database service tests."""

import pytest

from dt.data.database.app import create_app
from dt.data.database.timescale_storage import TimescaleStorage
from dt.utils import Config


@pytest.fixture
def storage(clean_timescale_storage: TimescaleStorage) -> TimescaleStorage:
    """Create a TimescaleStorage instance with a clean database.

    Parameters
    ----------
    clean_timescale_storage : TimescaleStorage
        Storage instance backed by a clean database schema.

    Returns
    -------
    TimescaleStorage
        Storage instance backed by a clean database schema.
    """
    return clean_timescale_storage


@pytest.fixture
def client(storage: TimescaleStorage):
    """Create a Flask test client backed by the real storage implementation.

    Parameters
    ----------
    storage : TimescaleStorage
        Storage instance used by the app under test.

    Returns
    -------
    flask.testing.FlaskClient
        Client for issuing HTTP requests to the database API.
    """
    app = create_app(config=Config, storage=storage)
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def sample_plant_id(storage: TimescaleStorage) -> int:
    """Create a sample plant for database tests.

    Parameters
    ----------
    storage : TimescaleStorage
        Storage instance for persisting the sample plant.

    Returns
    -------
    int
        Plant identifier.
    """
    return storage.upsert_plant(name="Test Plant", notes="Database tests")


@pytest.fixture
def sample_sensor(storage: TimescaleStorage, sample_plant_id: int):
    """Create a sample sensor descriptor registered in the database.

    Parameters
    ----------
    storage : TimescaleStorage
        Storage instance used to register the sensor.
    sample_plant_id : int
        Plant identifier owning the sensor.

    Returns
    -------
    dt.communication.dataclasses.SensorDescriptor
        Registered sensor descriptor with ID assigned.
    """
    from dt.communication.dataclasses import SensorDescriptor

    sensor = SensorDescriptor(
        id=0,
        plant_id=sample_plant_id,
        name="test_sensor",
        pin=7,
        read_interval=60,
    )
    sensor_id = storage.register_sensor(sensor)
    sensor.id = sensor_id
    return sensor
