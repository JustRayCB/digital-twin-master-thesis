from unittest.mock import MagicMock, patch

import pytest
import requests

from dt.communication.dataclasses.sensor import SensorDescriptor
from dt.communication.db_client import DatabaseApiClient


def test_bind_sensor_posts_payload_and_returns_sensor_id() -> None:
    """Bind a sensor and return the storage-assigned ID.

    Returns
    -------
    None
        Assertions fail if request payload or parsing regresses.
    """
    client = DatabaseApiClient(base_url="http://localhost:5001")
    sensor = SensorDescriptor(id=0, plant_id=1, name="dht22.temperature", pin=17, read_interval=5)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"sensor_id": 42}
    mock_response.raise_for_status.return_value = None

    with patch("requests.post", return_value=mock_response) as mock_post:
        sensor_id = client.bind_sensor(sensor)

    assert sensor_id == 42
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "http://localhost:5001/bind_sensor"
    assert kwargs["headers"] == {"Content-Type": "application/json"}
    assert kwargs["timeout"] == 5
    assert kwargs["json"]["name"] == "dht22.temperature"


def test_bind_sensor_returns_minus_one_when_response_missing_sensor_id() -> None:
    """Return -1 when the backend omits sensor_id in its response.

    Returns
    -------
    None
        Assertions fail if missing keys stop being handled.
    """
    client = DatabaseApiClient(base_url="http://localhost:5001")
    sensor = SensorDescriptor(id=0, plant_id=1, name="dht22.temperature", pin=17, read_interval=5)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_response.raise_for_status.return_value = None

    with patch("requests.post", return_value=mock_response):
        sensor_id = client.bind_sensor(sensor)

    assert sensor_id == -1


def test_bind_sensor_wraps_request_exceptions() -> None:
    """Raise RuntimeError when the HTTP request fails.

    Returns
    -------
    None
        Assertions fail if error mapping changes.
    """
    client = DatabaseApiClient(base_url="http://localhost:5001")
    sensor = SensorDescriptor(id=0, plant_id=1, name="dht22.temperature", pin=17, read_interval=5)

    with patch("requests.post", side_effect=requests.RequestException("boom")):
        with pytest.raises(RuntimeError, match="Failed to bind sensor"):
            client.bind_sensor(sensor)


def test_list_sensors_gets_and_structures_payload() -> None:
    """List sensors and coerce types via SensorDescriptor.__post_init__.

    Returns
    -------
    None
        Assertions fail if structuring changes.
    """
    client = DatabaseApiClient(base_url="http://localhost:5001")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"id": "7", "plant_id": "1", "name": "dht22.temperature", "pin": "17", "read_interval": "5"},
        {"id": 8, "plant_id": 1, "name": "bh1750.lux", "pin": 4, "read_interval": 60, "status": "active"},
    ]
    mock_response.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_response) as mock_get:
        sensors = client.list_sensors()

    mock_get.assert_called_once_with(
        "http://localhost:5001/sensors",
        headers={"Content-Type": "application/json"},
        timeout=5,
    )
    assert [s.id for s in sensors] == [7, 8]
    assert sensors[0].pin == 17
    assert sensors[0].read_interval == 5


def test_list_sensors_wraps_request_exceptions() -> None:
    """Raise RuntimeError when listing sensors fails.

    Returns
    -------
    None
        Assertions fail if error mapping changes.
    """
    client = DatabaseApiClient(base_url="http://localhost:5001")

    with patch("requests.get", side_effect=requests.RequestException("boom")):
        with pytest.raises(RuntimeError, match="Failed to list sensors"):
            client.list_sensors()


def test_list_actuators_gets_payload() -> None:
    """List actuators and return backend dicts without structuring.

    Returns
    -------
    None
        Assertions fail if request parameters regress.
    """
    client = DatabaseApiClient(base_url="http://localhost:5001")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"id": 1, "name": "pump"}]
    mock_response.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_response) as mock_get:
        actuators = client.list_actuators()

    mock_get.assert_called_once_with(
        "http://localhost:5001/actuators",
        headers={"Content-Type": "application/json"},
        timeout=5,
    )
    assert actuators == [{"id": 1, "name": "pump"}]


def test_list_actuators_wraps_request_exceptions() -> None:
    """Raise RuntimeError when listing actuators fails.

    Returns
    -------
    None
        Assertions fail if error mapping changes.
    """
    client = DatabaseApiClient(base_url="http://localhost:5001")

    with patch("requests.get", side_effect=requests.RequestException("boom")):
        with pytest.raises(RuntimeError, match="Failed to list actuators"):
            client.list_actuators()
