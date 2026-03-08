"""Integration tests for sensor and actuator database API client methods."""

from __future__ import annotations

import pytest

from dt.communication.dataclasses.sensor import SensorDescriptor
from dt.communication.db_client import DatabaseApiClient
from dt.data.database.timescale_storage import TimescaleStorage

pytestmark = [pytest.mark.requires_timescale]


def test_bind_sensor_persists_and_returns_sensor_id(
    database_api_client: DatabaseApiClient,
    test_storage: TimescaleStorage,
    plant_id: int,
) -> None:
    """Bind a sensor through the real database API and persist it."""
    sensor = SensorDescriptor(
        id=0,
        plant_id=plant_id,
        name="dht22.temperature",
        pin=17,
        read_interval=5,
    )

    sensor_id = database_api_client.bind_sensor(sensor)

    assert sensor_id > 0
    sensors = test_storage.list_sensors()
    assert any(item.id == sensor_id and item.name == sensor.name for item in sensors)


def test_list_sensors_reads_real_api_payload(
    database_api_client: DatabaseApiClient,
    sensor: SensorDescriptor,
) -> None:
    """List sensors through the real database API and deserialize descriptors."""
    sensors = database_api_client.list_sensors()

    assert [item.id for item in sensors] == [sensor.id]
    assert sensors[0].pin == sensor.pin
    assert sensors[0].read_interval == sensor.read_interval


def test_list_actuators_reads_real_api_payload(
    database_api_client: DatabaseApiClient,
    test_storage: TimescaleStorage,
    plant_id: int,
) -> None:
    """List actuators through the real database API."""
    actuator_id = test_storage.register_actuator(plant_id, "pump", 18, 0)

    actuators = database_api_client.list_actuators()

    assert actuators == [
        {
            "id": actuator_id,
            "plant_id": plant_id,
            "name": "pump",
            "pin": 18,
            "relay_channel": 0,
            "status": "active",
        }
    ]


def test_bind_sensor_wraps_real_request_exceptions(plant_id: int) -> None:
    """Raise RuntimeError when the sensor-binding API cannot be reached."""
    client = DatabaseApiClient(base_url="http://127.0.0.1:9")
    sensor = SensorDescriptor(
        id=0,
        plant_id=plant_id,
        name="dht22.temperature",
        pin=17,
        read_interval=5,
    )

    with pytest.raises(RuntimeError, match="Failed to bind sensor"):
        client.bind_sensor(sensor)


def test_list_sensors_wraps_real_request_exceptions() -> None:
    """Raise RuntimeError when the sensor-list API cannot be reached."""
    client = DatabaseApiClient(base_url="http://127.0.0.1:9")

    with pytest.raises(RuntimeError, match="Failed to list sensors"):
        client.list_sensors()


def test_list_actuators_wraps_real_request_exceptions() -> None:
    """Raise RuntimeError when the actuator-list API cannot be reached."""
    client = DatabaseApiClient(base_url="http://127.0.0.1:9")

    with pytest.raises(RuntimeError, match="Failed to list actuators"):
        client.list_actuators()
