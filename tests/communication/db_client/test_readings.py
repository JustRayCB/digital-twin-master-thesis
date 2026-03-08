"""Integration tests for reading queries through the database API client."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from dt.communication.dataclasses.aggregated_reading import AggregatedReading
from dt.communication.dataclasses.processed_sensor_data import ProcessedSensorData
from dt.communication.dataclasses.queries import ReadingsQuery
from dt.communication.db_client import DatabaseApiClient
from dt.communication.topics import Topics
from dt.data.database.timescale_storage import TimescaleStorage

pytestmark = [pytest.mark.requires_timescale]


def test_query_readings_raw_structures_processed_readings(
    database_api_client: DatabaseApiClient,
    storage: TimescaleStorage,
    reading: ProcessedSensorData,
) -> None:
    """Query raw readings and deserialize ProcessedSensorData instances."""
    storage.ingest_reading(reading)

    readings = database_api_client.query_readings(
        ReadingsQuery(
            window="raw",
            sensor_id=reading.sensor_id,
            plant_id=reading.plant_id,
            topic=reading.topic.value,
        )
    )

    assert len(readings) == 1
    assert isinstance(readings[0], ProcessedSensorData)
    assert readings[0].topic is Topics.TEMPERATURE


def test_query_readings_1h_structures_aggregated_readings(
    database_api_client: DatabaseApiClient,
    storage: TimescaleStorage,
    reading: ProcessedSensorData,
) -> None:
    """Query 1h aggregates and deserialize AggregatedReading instances."""
    storage.ingest_reading(reading)
    with storage.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("CALL refresh_continuous_aggregate('sensor_readings_1h', NULL, NULL);"))

    readings = database_api_client.query_readings(
        ReadingsQuery(
            window="1h",
            sensor_id=reading.sensor_id,
            plant_id=reading.plant_id,
            topic=reading.topic.value,
        )
    )

    assert len(readings) == 1
    assert isinstance(readings[0], AggregatedReading)
    assert readings[0].topic is Topics.TEMPERATURE


def test_query_readings_wraps_real_request_exceptions() -> None:
    """Raise RuntimeError when the readings API cannot be reached."""
    client = DatabaseApiClient(base_url="http://127.0.0.1:9")

    with pytest.raises(RuntimeError, match="Failed to query readings"):
        client.query_readings(ReadingsQuery(window="raw", sensor_id=1))
