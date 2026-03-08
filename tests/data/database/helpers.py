"""Helper functions for database integration tests."""

from __future__ import annotations

import time
from collections.abc import Callable

from dt.communication.messaging_service import KafkaService


def wait_until(
    predicate: Callable[[], bool],
    timeout_seconds: float = 10.0,
    interval_seconds: float = 0.2,
) -> None:
    """Wait until a predicate returns True."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(interval_seconds)
    raise TimeoutError("Condition was not satisfied before timeout")


def wait_for_kafka_service_ready(bridge: KafkaService, expected_topics: set[str]) -> None:
    """Wait until the KafkaService consumer has joined and subscribed."""

    def is_ready() -> bool:
        if bridge.consumer is None:
            return False
        subscription = bridge.consumer.subscription()
        if not expected_topics.issubset(subscription):
            return False
        return bool(bridge.consumer.assignment())

    wait_until(is_ready, timeout_seconds=15.0, interval_seconds=0.25)
