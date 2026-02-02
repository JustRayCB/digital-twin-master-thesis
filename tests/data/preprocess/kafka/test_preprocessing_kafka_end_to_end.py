import json
import time
from datetime import datetime, timezone

import pytest
from kafka import KafkaAdminClient, KafkaConsumer, KafkaProducer
from kafka.admin import NewTopic
from kafka.errors import TopicAlreadyExistsError

from dt.communication.adapters import dump
from dt.communication.dataclasses.raw_sensor_data import RawSensorData
from dt.communication.topics import Topics
from dt.data.preprocess import main as preprocess_main
from dt.data.preprocess.config.manager import ConfigurationManager
from dt.data.preprocess.spark_adapter import SparkStreamingAdapter


@pytest.fixture(scope="module")
def kafka_container():
    """Start a Kafka container for end-to-end preprocessing tests."""
    try:
        from testcontainers.kafka import KafkaContainer

        with KafkaContainer().with_kraft() as kafka:
            yield kafka
    except Exception as exc:
        pytest.skip(f"Kafka test container could not start in this environment: {exc}")


@pytest.fixture(scope="module")
def kafka_bootstrap_servers(kafka_container) -> str:
    """Return Kafka bootstrap servers string."""
    return kafka_container.get_bootstrap_server()


@pytest.fixture(scope="module")
def kafka_topics(kafka_bootstrap_servers: str) -> list[str]:
    """Create raw/processed topics required by preprocessing."""
    raw_topic = Topics.TEMPERATURE.raw
    processed_topic = Topics.TEMPERATURE.processed

    admin = KafkaAdminClient(
        bootstrap_servers=kafka_bootstrap_servers, client_id="preprocess-tests-admin"
    )
    existing = set(admin.list_topics())
    to_create = [
        NewTopic(name=topic, num_partitions=1, replication_factor=1)
        for topic in (raw_topic, processed_topic)
        if topic not in existing
    ]
    if to_create:
        try:
            admin.create_topics(to_create)
        except TopicAlreadyExistsError:
            pass
    admin.close()

    return [raw_topic, processed_topic]


def test_preprocessing_kafka_end_to_end(
    spark_session,
    tmp_path,
    test_config_path,
    configure_preprocess_db_client,
    sensor_registry,
    kafka_bootstrap_servers,
    kafka_topics,
) -> None:
    """Raw Kafka events should be processed and published to processed topics."""
    sensor = sensor_registry["register"]("dht22.temperature")
    raw_topic, processed_topic = kafka_topics

    adapter = SparkStreamingAdapter(ConfigurationManager(test_config_path))
    try:
        raw_events = preprocess_main._read_raw_events(
            spark_session,
            kafka_bootstrap=kafka_bootstrap_servers,
            topic_pattern=raw_topic,
            starting_offsets="earliest",
        )
    except Exception as exc:
        if "Failed to find data source: kafka" in str(exc):
            pytest.skip("Spark Kafka integration is unavailable in this environment.")
        raise
    processed_stream = adapter.build_preprocessing_stream(spark_session, raw_events)
    kafka_ready = preprocess_main._prepare_kafka_sink(
        processed_stream, preprocess_main._build_topic_map()
    )

    checkpoint_dir = tmp_path / "kafka_checkpoint"
    query = (
        kafka_ready.writeStream.format("kafka")
        .option("kafka.bootstrap.servers", kafka_bootstrap_servers)
        .option("checkpointLocation", str(checkpoint_dir))
        .outputMode("update")
        .start()
    )

    producer = KafkaProducer(
        bootstrap_servers=kafka_bootstrap_servers,
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
    )
    consumer = KafkaConsumer(
        processed_topic,
        bootstrap_servers=kafka_bootstrap_servers,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
    )

    try:
        raw_payload = RawSensorData(
            plant_id=sensor.plant_id,
            sensor_id=sensor.id,
            timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp(),
            value=22.5,
            unit="°C",
            topic=Topics.TEMPERATURE,
            correlation_id="kafka-1",
        )
        producer.send(raw_topic, dump("generic", raw_payload))
        producer.flush()

        deadline = time.time() + 30
        received = None
        while time.time() < deadline and received is None:
            records = consumer.poll(timeout_ms=1000)
            for messages in records.values():
                if messages:
                    received = messages[0].value
                    break

        assert received is not None
        assert received["sensor_id"] == sensor.id
        assert received["plant_id"] == sensor.plant_id
        assert received["raw_value"] == 22.5
        assert received["flags"]["valid_data_point"] is True
        assert received["topic"] == Topics.TEMPERATURE.value
    finally:
        query.stop()
        producer.close()
        consumer.close()
