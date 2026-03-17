"""Integration tests for reading queries through the database API client."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from dt.communication.dataclasses.aggregated_reading import AggregatedReading
from dt.communication.dataclasses.processed_sensor_data import ProcessedSensorData
from dt.communication.dataclasses.queries import ReadingsQuery
from dt.communication.db_client import DatabaseApiClient
from dt.communication.topics import Topics

pytestmark = [pytest.mark.requires_timescale]


def test_query_readings_raw_structures_processed_readings(
    database_api_client: DatabaseApiClient,
    readings_store,
    reading: ProcessedSensorData,
) -> None:
    """Query raw readings and deserialize ProcessedSensorData instances."""
    readings_store.ingest_reading(reading)

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
    readings_store,
    reading: ProcessedSensorData,
) -> None:
    """Query 1h aggregates and deserialize AggregatedReading instances."""
    readings_store.ingest_reading(reading)
    with readings_store.engine.connect().execution_options(
        isolation_level="AUTOCOMMIT"
    ) as conn:
        conn.execute(
            text("CALL refresh_continuous_aggregate('sensor_readings_1h', NULL, NULL);")
        )

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
    assert readings[0].mean_value == pytest.approx(reading.value)
    assert readings[0].sample_count == 1
    assert readings[0].variance_value is None
    assert readings[0].stddev_value is None
    assert readings[0].skewness_value is None


def test_query_readings_1h_includes_avg_series(
    database_api_client: DatabaseApiClient,
    readings_store,
    reading: ProcessedSensorData,
) -> None:
    """1h aggregates include avg_raw_value, avg_calibrated_value, avg_normalized_value."""
    reading.raw_value = 20.0
    reading.calibrated_value = 21.0
    reading.normalized_value = 0.5
    readings_store.ingest_reading(reading)
    with readings_store.engine.connect().execution_options(
        isolation_level="AUTOCOMMIT"
    ) as conn:
        conn.execute(
            text("CALL refresh_continuous_aggregate('sensor_readings_1h', NULL, NULL);")
        )

    readings = database_api_client.query_readings(
        ReadingsQuery(
            window="1h",
            sensor_id=reading.sensor_id,
            plant_id=reading.plant_id,
            topic=reading.topic.value,
        )
    )

    assert len(readings) == 1
    agg = readings[0]
    assert isinstance(agg, AggregatedReading)
    assert agg.avg_raw_value == pytest.approx(20.0)
    assert agg.avg_calibrated_value == pytest.approx(21.0)
    assert agg.avg_normalized_value == pytest.approx(0.5)


def test_query_readings_wraps_real_request_exceptions() -> None:
    """Raise RuntimeError when the readings API cannot be reached."""
    client = DatabaseApiClient(base_url="http://127.0.0.1:9")

    with pytest.raises(RuntimeError, match="Failed to query readings"):
        client.query_readings(ReadingsQuery(window="raw", sensor_id=1))
