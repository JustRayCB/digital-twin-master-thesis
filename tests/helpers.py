"""Shared helper functions for test modules."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Callable

from kafka import KafkaAdminClient, KafkaConsumer, KafkaProducer
from kafka.admin import NewTopic
from kafka.errors import TopicAlreadyExistsError


def wait_for_consumer_assignment(consumer: KafkaConsumer, timeout_seconds: float = 5.0) -> None:
    """Wait for a Kafka consumer to receive a partition assignment."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        consumer.poll(timeout_ms=200)
        if consumer.assignment():
            return
    raise TimeoutError("Kafka consumer did not receive a partition assignment")


def ensure_kafka_topics(
    kafka_bootstrap_servers: str, topics: set[str], *, warm_topics: bool = True
) -> list[str]:
    """Create Kafka topics needed by tests and optionally publish a warm-up record."""
    admin = KafkaAdminClient(
        bootstrap_servers=kafka_bootstrap_servers, client_id="integration-tests-admin"
    )
    existing = set(admin.list_topics())
    to_create = [
        NewTopic(name=topic, num_partitions=1, replication_factor=1)
        for topic in topics
        if topic not in existing
    ]
    if to_create:
        try:
            admin.create_topics(to_create)
        except TopicAlreadyExistsError:
            pass
    admin.close()

    if warm_topics:
        producer = KafkaProducer(
            bootstrap_servers=kafka_bootstrap_servers,
            value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        )
        for topic in topics:
            producer.send(topic, {})
        producer.flush()
        producer.close()

    return sorted(topics)


def create_topic_consumer(
    topic: str,
    kafka_bootstrap_servers: str,
    group_prefix: str,
    auto_offset_reset: str = "latest",
    enable_auto_commit: bool = True,
    value_deserializer: Callable[[bytes], Any] | None = None,
) -> KafkaConsumer:
    """Create a Kafka consumer for a single topic and wait for assignment."""
    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=kafka_bootstrap_servers,
        group_id=f"{group_prefix}-{uuid.uuid4().hex[:8]}",
        auto_offset_reset=auto_offset_reset,
        enable_auto_commit=enable_auto_commit,
        value_deserializer=value_deserializer or (lambda value: json.loads(value.decode("utf-8"))),
    )
    wait_for_consumer_assignment(consumer)
    return consumer
