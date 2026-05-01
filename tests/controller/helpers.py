"""Helper functions for controller integration tests."""

from __future__ import annotations

import time

from kafka import KafkaConsumer

from dt.communication.dataclasses.controller import ActionCommand
from dt.communication.dataclasses.queries import ActionHistoryQuery
from dt.communication.db_client import DatabaseApiClient


def poll_action_messages(
    consumer: KafkaConsumer,
    expected_count: int,
    timeout_seconds: float = 5.0,
    *,
    action_id: str | None = None,
) -> list[dict]:
    """Poll Kafka for a sequence of action messages."""
    deadline = time.time() + timeout_seconds
    messages: list[dict] = []
    while time.time() < deadline and len(messages) < expected_count:
        records = consumer.poll(timeout_ms=500)
        for batches in records.values():
            for message in batches:
                payload = message.value
                if not isinstance(payload, dict):
                    continue
                if action_id is not None and payload.get("action_id") != action_id:
                    continue
                messages.append(payload)
                if len(messages) >= expected_count:
                    return messages
    return messages


def wait_for_action_history(
    database_client: DatabaseApiClient,
    plant_id: int,
    predicate,
    *,
    limit: int = 10,
    timeout_seconds: float = 10.0,
) -> list[ActionCommand]:
    """Poll the database API until action history matches a predicate."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        history = database_client.get_action_history(
            ActionHistoryQuery(plant_id=plant_id, limit=limit)
        )
        if predicate(history):
            return history
        time.sleep(0.25)
    raise TimeoutError("Action history condition was not satisfied before timeout")
