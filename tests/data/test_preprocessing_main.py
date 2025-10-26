import json
from datetime import datetime, timezone

import pytest
from pyspark.sql import SparkSession

from dt.communication.dataclasses.processed_sensor_data import (
    ProcessedSensorData, ValidationFlag)
from dt.communication.topics import Topics
from dt.data.preprocess import main as preprocess_main


@pytest.fixture(scope="module")
def spark_session() -> SparkSession:
    session = (
        SparkSession.builder.master("local[*]")
        .appName("preprocessing-main-tests")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


def test_prepare_kafka_sink_routes_to_processed_topic(spark_session: SparkSession) -> None:
    """Ensure the sink remaps to processed topics while preserving payload contents."""

    schema = ProcessedSensorData.get_spark_schema()
    base_topic = Topics.TEMPERATURE.value
    processed_topic = Topics.TEMPERATURE.processed
    timestamp = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
    flags = {flag.value: (flag is ValidationFlag.VALID) for flag in ValidationFlag}

    processed_df = spark_session.createDataFrame(
        [
            (
                1,
                101,
                timestamp,
                23.5,
                "C",
                base_topic,
                "corr-1",
                flags,
                0.95,
                False,
                None,
            )
        ],
        schema=schema,
    )

    topic_map = {base_topic: processed_topic}

    result_df = preprocess_main._prepare_kafka_sink(processed_df, topic_map)

    rows = result_df.collect()
    assert len(rows) == 1
    row = rows[0]

    assert row["topic"] == processed_topic

    payload = json.loads(row["value"])
    assert payload["topic"] == base_topic
    assert payload["plant_id"] == 1
    assert payload["sensor_id"] == 101
    assert payload["value"] == 23.5
