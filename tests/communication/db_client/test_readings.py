"""Integration tests for reading queries through the database API client."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from dt.communication.dataclasses import SensorDescriptor
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


def test_query_readings_1h_combines_same_topic_across_sensors(
    database_api_client: DatabaseApiClient,
    readings_store,
    reading: ProcessedSensorData,
    metadata_store,
) -> None:
    """1h query stats are computed from the combined same-topic hourly series."""
    readings_store.ingest_reading(reading)

    sensor_two = metadata_store.register_sensor(
        SensorDescriptor(
            id=-1,
            plant_id=reading.plant_id,
            name="dht22.temperature.2",
            pin=18,
            read_interval=5,
        )
    )
    readings_store.ingest_reading(
        ProcessedSensorData(
            plant_id=reading.plant_id,
            sensor_id=sensor_two,
            timestamp=reading.timestamp + 60,
            value=24.0,
            unit=reading.unit,
            topic=reading.topic,
            correlation_id="corr-2",
            flags=reading.flags,
            dq_score=reading.dq_score,
            imputed=False,
        )
    )

    with readings_store.engine.connect().execution_options(
        isolation_level="AUTOCOMMIT"
    ) as conn:
        conn.execute(
            text("CALL refresh_continuous_aggregate('sensor_readings_1h', NULL, NULL);")
        )

    readings = database_api_client.query_readings(
        ReadingsQuery(
            window="1h",
            plant_id=reading.plant_id,
            topic=reading.topic.value,
            since=reading.timestamp - 3600,
            until=reading.timestamp + 3600,
        )
    )

    assert len(readings) == 1
    aggregate = readings[0]
    assert isinstance(aggregate, AggregatedReading)
    assert aggregate.sample_count == 2
    assert aggregate.mean_value == pytest.approx((reading.value + 24.0) / 2.0)
    assert aggregate.min_value == pytest.approx(min(reading.value, 24.0))
    assert aggregate.max_value == pytest.approx(max(reading.value, 24.0))
    assert aggregate.variance_value == pytest.approx(3.125)
    assert aggregate.stddev_value == pytest.approx(3.125**0.5)


def test_query_readings_wraps_real_request_exceptions() -> None:
    """Raise RuntimeError when the readings API cannot be reached."""
    client = DatabaseApiClient(base_url="http://127.0.0.1:9")

    with pytest.raises(RuntimeError, match="Failed to query readings"):
        client.query_readings(ReadingsQuery(window="raw", sensor_id=1))
