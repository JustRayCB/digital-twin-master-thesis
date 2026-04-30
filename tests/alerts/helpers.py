"""Helper functions for alert engine tests."""

from __future__ import annotations

import time
from contextlib import contextmanager

from kafka import KafkaConsumer

from dt.analytics.alerts.evaluator import RuleEvaluator
from dt.analytics.alerts.publisher import AlertPublisher
from dt.analytics.alerts.registry import AlertRegistry
from dt.communication.adapters import load
from dt.communication.dataclasses import ProcessedSensorData, SensorDescriptor
from dt.communication.dataclasses.alerts.alert_record import (
    AlertHistoryEvent,
    ExternalAlertEvent,
    SensorAlertEvent,
)
from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.messaging_service import KafkaService
from dt.communication.topics import Topics


def load_alert_event(payload: dict) -> AlertHistoryEvent:
    """Deserialize alert payloads into alert event types."""
    if "reading" in payload:
        return load("generic", SensorAlertEvent, payload)
    if "metadata" in payload:
        return load("generic", ExternalAlertEvent, payload)
    return load("generic", AlertHistoryEvent, payload)


def poll_alert_event(
    consumer: KafkaConsumer, timeout_seconds: float = 5.0
) -> AlertHistoryEvent | None:
    """Poll Kafka for the next alert event."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        records = consumer.poll(timeout_ms=500)
        for messages in records.values():
            for message in messages:
                return load_alert_event(message.value)
    return None


def collect_alert_events(
    consumer: KafkaConsumer, count: int, timeout_seconds: float = 5.0
) -> list[AlertHistoryEvent]:
    """Collect a number of alert events from Kafka."""
    events: list[AlertHistoryEvent] = []
    deadline = time.time() + timeout_seconds
    while len(events) < count and time.time() < deadline:
        records = consumer.poll(timeout_ms=500)
        for messages in records.values():
            for message in messages:
                events.append(load_alert_event(message.value))
                if len(events) >= count:
                    break
    return events


def build_processed_reading(
    sensor: SensorDescriptor,
    value: float,
    dq_score: float = 1.0,
    correlation_id: str = "test-corr-1",
) -> ProcessedSensorData:
    """Build a processed sensor reading for alert tests."""
    return ProcessedSensorData(
        plant_id=sensor.plant_id,
        sensor_id=sensor.id,
        timestamp=time.time(),
        value=value,
        unit="Celsius",
        topic=Topics.TEMPERATURE,
        correlation_id=correlation_id,
        flags={ValidationFlag.VALID: True},
        dq_score=dq_score,
        imputed=False,
    )


def wait_for_consumer_thread(consumer_service: KafkaService, timeout_seconds: float = 5.0) -> None:
    """Wait for a KafkaService consumer thread to start polling."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if consumer_service.consumer and consumer_service.consumer_thread:
            if consumer_service.consumer_thread.is_alive():
                time.sleep(1.2)
                return
        time.sleep(0.05)
    raise AssertionError("Kafka consumer thread did not start within timeout.")


def wait_for_alert_state(registry: AlertRegistry, alert_key: str, timeout_seconds: float = 5.0):
    """Wait for an alert state to appear in the registry."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        state = registry.get_alert_state(alert_key)
        if state is not None:
            return state
        time.sleep(0.1)
    return None


@contextmanager
def running_alert_service(
    consumer_service: KafkaService,
    evaluator: RuleEvaluator,
    registry: AlertRegistry,
    publisher: AlertPublisher,
):
    """Run the alert engine service and ensure shutdown."""
    from dt.analytics.alerts.service import AlertEngineService

    service = AlertEngineService(
        kafka_service=consumer_service,
        evaluator=evaluator,
        registry=registry,
        publisher=publisher,
    )
    service.start()
    wait_for_consumer_thread(consumer_service)
    try:
        yield service
    finally:
        service.shutdown()
