"""Shared fixtures for database service tests."""

import pytest

from dt.data.database.app import create_app
from dt.utils import Config


@pytest.fixture
def client(test_storage):
    """Create a Flask test client backed by the real storage implementation.

    Parameters
    ----------
    test_storage : TimescaleStorage
        Storage instance used by the app under test.

    Returns
    -------
    flask.testing.FlaskClient
        Client for issuing HTTP requests to the database API.
    """
    app = create_app(config=Config, storage=test_storage)
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def sample_plant_id(test_storage) -> int:
    """Create a sample plant for database tests.

    Parameters
    ----------
    test_storage : TimescaleStorage
        Storage instance for persisting the sample plant.

    Returns
    -------
    int
        Plant identifier.
    """
    return test_storage.upsert_plant(name="Test Plant", notes="Database tests")


@pytest.fixture
def sample_sensor(test_storage, sample_plant_id: int):
    """Create a sample sensor descriptor registered in the database.

    Parameters
    ----------
    test_storage : TimescaleStorage
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
    sensor_id = test_storage.register_sensor(sensor)
    sensor.id = sensor_id
    return sensor
