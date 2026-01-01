from unittest.mock import MagicMock, patch

import pytest
import requests

from dt.communication.dataclasses.aggregated_reading import AggregatedReading
from dt.communication.dataclasses.processed_sensor_data import ProcessedSensorData
from dt.communication.dataclasses.queries import ReadingsQuery
from dt.communication.db_client import DatabaseApiClient
from dt.communication.topics import Topics


def test_query_readings_raw_structures_processed_readings() -> None:
    """Query raw readings and structure ProcessedSensorData objects.

    Returns
    -------
    None
        Assertions fail if request parameters or structuring changes.
    """
    client = DatabaseApiClient(base_url="http://localhost:5001")
    query = ReadingsQuery(window="raw", sensor_id=1, plant_id=2, topic=Topics.TEMPERATURE.value)

    payload = [
        {
            "plant_id": 2,
            "sensor_id": 1,
            "timestamp": 1_735_000_000.0,
            "value": 21.5,
            "unit": "C",
            "topic": Topics.TEMPERATURE.value,
            "correlation_id": "corr-1",
            "flags": {"valid_data_point": True},
            "dq_score": 0.9,
            "imputed": False,
        }
    ]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = payload
    mock_response.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_response) as mock_get:
        readings = client.query_readings(query)

    mock_get.assert_called_once_with(
        "http://localhost:5001/readings",
        params={
            "window": "raw",
            "sensor_id": 1,
            "plant_id": 2,
            "topic": Topics.TEMPERATURE.value,
            "since": None,
            "until": None,
        },
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    assert len(readings) == 1
    assert isinstance(readings[0], ProcessedSensorData)
    assert readings[0].topic is Topics.TEMPERATURE


def test_query_readings_1h_structures_aggregated_readings() -> None:
    """Query 1h aggregates and structure AggregatedReading objects.

    Returns
    -------
    None
        Assertions fail if aggregation window routing regresses.
    """
    client = DatabaseApiClient(base_url="http://localhost:5001")
    query = ReadingsQuery(window="1h", sensor_id=1, plant_id=2, topic=Topics.TEMPERATURE.value)

    payload = [
        {
            "bucket": 1_735_000_000.0,
            "sensor_id": 1,
            "plant_id": 2,
            "topic": Topics.TEMPERATURE.value,
            "unit": "C",
            "avg_value": 20.0,
            "min_value": 18.0,
            "max_value": 22.0,
            "sample_count": 12,
            "avg_dq_score": 0.95,
            "imputed_count": 1,
        }
    ]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = payload
    mock_response.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_response):
        readings = client.query_readings(query)

    assert len(readings) == 1
    assert isinstance(readings[0], AggregatedReading)
    assert readings[0].topic is Topics.TEMPERATURE


def test_query_readings_wraps_request_exceptions() -> None:
    """Raise RuntimeError when querying readings fails.

    Returns
    -------
    None
        Assertions fail if error mapping changes.
    """
    client = DatabaseApiClient(base_url="http://localhost:5001")
    query = ReadingsQuery(window="raw", sensor_id=1)

    with patch("requests.get", side_effect=requests.RequestException("boom")):
        with pytest.raises(RuntimeError, match="Failed to query readings"):
            client.query_readings(query)
