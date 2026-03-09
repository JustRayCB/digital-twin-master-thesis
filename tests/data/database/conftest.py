"""Shared fixtures for database service tests."""

import pytest

from dt.data.database.app import create_app
from dt.utils import Config


@pytest.fixture
def client(
    metadata_store,
    readings_store,
    alert_store,
    controller_store,
    snapshot_store,
):
    """Create a Flask test client backed by the real storage implementations.

    Parameters
    ----------
    metadata_store, readings_store, alert_store, controller_store, snapshot_store
        Dedicated stores used by the app under test.

    Returns
    -------
    flask.testing.FlaskClient
        Client for issuing HTTP requests to the database API.
    """
    app = create_app(
        config=Config,
        metadata_storage=metadata_store,
        readings_storage=readings_store,
        alert_storage=alert_store,
        controller_storage=controller_store,
        snapshot_storage=snapshot_store,
    )
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def sample_plant_id(metadata_store) -> int:
    """Create a sample plant for database tests.

    Parameters
    ----------
    metadata_store : MetadataStore
        Store used for persisting the sample plant.

    Returns
    -------
    int
        Plant identifier.
    """
    return metadata_store.upsert_plant(name="Test Plant", notes="Database tests")


@pytest.fixture
def sample_sensor(metadata_store, sample_plant_id: int):
    """Create a sample sensor descriptor registered in the database.

    Parameters
    ----------
    metadata_store : MetadataStore
        Store used to register the sensor.
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
    sensor_id = metadata_store.register_sensor(sensor)
    sensor.id = sensor_id
    return sensor
