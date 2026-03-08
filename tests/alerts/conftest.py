"""Shared fixtures for alert engine tests."""

from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager

import pytest
from kafka import KafkaConsumer

from dt.alerts.evaluator import RuleEvaluator
from dt.alerts.publisher import AlertPublisher
from dt.alerts.registry import AlertRegistry
from dt.alerts.rules import (AlertCondition, AlertRule, ConditionType,
                             EvaluationStage, SeverityLevel)
from dt.communication.adapters import load
from dt.communication.dataclasses import ProcessedSensorData, SensorDescriptor
from dt.communication.dataclasses.alerts.alert_record import (
    AlertDefinition, AlertHistoryEvent, AlertStatus, ExternalAlertEvent,
    SensorAlertEvent)
from dt.communication.dataclasses.alerts.alert_type import AlertType
from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.db_client import DatabaseApiClient
from dt.communication.messaging_service import KafkaService
from dt.communication.topics import Topics
from tests.conftest import wait_for_consumer_assignment


def load_alert_event(payload: dict) -> AlertHistoryEvent:
    """Deserialize alert payloads into alert event types.

    Parameters
    ----------
    payload : dict
        Serialized alert payload from Kafka.

    Returns
    -------
    AlertHistoryEvent
        Structured alert event instance.
    """
    if "reading" in payload:
        return load("generic", SensorAlertEvent, payload)
    if "metadata" in payload:
        return load("generic", ExternalAlertEvent, payload)
    return load("generic", AlertHistoryEvent, payload)


def poll_alert_event(
    consumer: KafkaConsumer, timeout_seconds: float = 5.0
) -> AlertHistoryEvent | None:
    """Poll Kafka for the next alert event.

    Parameters
    ----------
    consumer : KafkaConsumer
        Consumer subscribed to the alerts topic.
    timeout_seconds : float, optional
        Maximum time to wait for a message.

    Returns
    -------
    AlertHistoryEvent | None
        Parsed alert event, or None if no message arrives in time.
    """
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
    """Collect a number of alert events from Kafka.

    Parameters
    ----------
    consumer : KafkaConsumer
        Consumer subscribed to the alerts topic.
    count : int
        Number of events to collect.
    timeout_seconds : float, optional
        Maximum time to wait for the events.

    Returns
    -------
    list[AlertHistoryEvent]
        Collected alert events.
    """
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
    """Build a processed sensor reading for alert tests.

    Parameters
    ----------
    sensor : SensorDescriptor
        Registered sensor used to populate the reading.
    value : float
        Sensor reading value.
    dq_score : float, optional
        Data-quality score for the reading.
    correlation_id : str, optional
        Correlation identifier propagated through the alert flow.

    Returns
    -------
    ProcessedSensorData
        Reading payload aligned with the alert service contracts.
    """
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
    from dt.alerts.service import AlertEngineService

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


@pytest.fixture
def alerts_consumer(kafka_bootstrap_servers, kafka_topics):
    """Create a Kafka consumer for alert events.

    Parameters
    ----------
    kafka_bootstrap_servers : str
        Kafka bootstrap server URL.

    Returns
    -------
    KafkaConsumer
        Consumer subscribed to the alerts topic.
    """
    consumer = KafkaConsumer(
        Topics.ALERTS,
        bootstrap_servers=kafka_bootstrap_servers,
        group_id=f"alert-tests-{uuid.uuid4().hex[:8]}",
        auto_offset_reset="latest",
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
    )
    wait_for_consumer_assignment(consumer)
    yield consumer
    consumer.close()


@pytest.fixture(scope="module")
def sample_plant_id(storage) -> int:
    """Create a sample plant in the test database.

    Parameters
    ----------
    storage : TimescaleStorage
        Storage instance backed by the test database.

    Returns
    -------
    int
        Plant identifier for alert tests.
    """
    return storage.upsert_plant(name="Alert Test Plant", notes="Alert service tests")


@pytest.fixture(scope="module")
def sample_sensor(storage, sample_plant_id) -> SensorDescriptor:
    """Create a sample sensor in the test database.

    Parameters
    ----------
    storage : TimescaleStorage
        Storage instance backed by the test database.
    sample_plant_id : int
        Plant identifier for the test sensor.

    Returns
    -------
    SensorDescriptor
        Registered sensor descriptor.
    """
    sensor = SensorDescriptor(
        id=0, plant_id=sample_plant_id, name="alert_sensor", pin=4, read_interval=60
    )
    sensor_id = storage.register_sensor(sensor)
    sensor.id = sensor_id
    return sensor


@pytest.fixture
def definition_client(database_service_base_url) -> DatabaseApiClient:
    """Create a DatabaseApiClient for the test database service.

    Parameters
    ----------
    database_service_base_url : str
        Base URL for the database service API.

    Returns
    -------
    DatabaseApiClient
        Client wired to the test database service.
    """
    return DatabaseApiClient(base_url=database_service_base_url)


@pytest.fixture
def sample_processed_data() -> ProcessedSensorData:
    """Create sample processed sensor data.

    Returns
    -------
    ProcessedSensorData
        Sample processed reading used across alert engine tests.
    """
    return ProcessedSensorData(
        plant_id=1,
        sensor_id=101,
        timestamp=1234567890.0,
        value=38.0,
        unit="Celsius",
        topic=Topics.TEMPERATURE,
        correlation_id="test-corr-123",
        flags={ValidationFlag.VALID: True},
        dq_score=0.95,
        imputed=False,
    )


@pytest.fixture
def sample_sensor_alert_event(sample_processed_data: ProcessedSensorData) -> SensorAlertEvent:
    """Create a sample sensor alert event.

    Parameters
    ----------
    sample_processed_data : ProcessedSensorData
        Reading used to populate the sensor alert event.

    Returns
    -------
    SensorAlertEvent
        Sample sensor alert event with threshold metadata.
    """
    return SensorAlertEvent(
        alert_key="temp_high:temperature",
        plant_id=sample_processed_data.plant_id,
        timestamp=sample_processed_data.timestamp,
        status=AlertStatus.ACTIVE,
        severity=SeverityLevel.WARNING,
        message="Temperature exceeds 35°C (actual: 38°C)",
        correlation_id=sample_processed_data.correlation_id,
        reading=sample_processed_data,
        threshold_op=">",
        threshold_value=35.0,
    )


@pytest.fixture
def sample_alert_definition(sample_processed_data: ProcessedSensorData) -> AlertDefinition:
    """Create a sample alert definition matching the sample event.

    Parameters
    ----------
    sample_processed_data : ProcessedSensorData
        Reading used to populate the definition metadata.

    Returns
    -------
    AlertDefinition
        Sample definition for sensor-based alerts.
    """
    return AlertDefinition(
        alert_key="temp_high:temperature",
        plant_id=sample_processed_data.plant_id,
        sensor_id=sample_processed_data.sensor_id,
        source=sample_processed_data.topic.short_name,
        rule_id="temp_high",
        rule_name="Temp High",
        kind=AlertType.SENSOR,
        persistence_count=1,
        cooldown_seconds=300,
    )


@pytest.fixture
def registry() -> AlertRegistry:
    """Create a fresh alert registry."""
    return AlertRegistry()


@pytest.fixture
def publisher_service(kafka_bootstrap_servers, kafka_topics):
    """Create a KafkaService for publishing alert events."""
    client_id = f"alert-publisher-{uuid.uuid4().hex[:8]}"
    service = KafkaService(host=kafka_bootstrap_servers, client_id=client_id, group_id=client_id)
    service.connect()
    yield service
    service.disconnect()


@pytest.fixture
def publisher(publisher_service, definition_client) -> AlertPublisher:
    """Create an alert publisher backed by Kafka and the database service."""
    return AlertPublisher(publisher_service, definition_client=definition_client)


@pytest.fixture
def consumer_service(kafka_bootstrap_servers, kafka_topics):
    """Create a KafkaService for consuming processed sensor data."""
    client_id = f"alert-consumer-{uuid.uuid4().hex[:8]}"
    return KafkaService(host=kafka_bootstrap_servers, client_id=client_id, group_id=client_id)


@pytest.fixture
def processed_publisher(kafka_service) -> KafkaService:
    """Provide a Kafka service for publishing processed sensor readings."""
    return kafka_service


@pytest.fixture
def threshold_rule() -> AlertRule:
    """Create a threshold-based alert rule."""
    return AlertRule(
        rule_id="temp_high",
        name="High Temperature Alert",
        description="Temperature exceeds {threshold}°C (actual: {value}°C)",
        severity=SeverityLevel.WARNING,
        evaluation_stage=EvaluationStage.PROCESSED,
        source="temperature",
        condition=AlertCondition(
            type=ConditionType.THRESHOLD,
            params={"operator": ">", "threshold": 35.0},
        ),
        persistence_count=2,
        cooldown_seconds=300,
    )


@pytest.fixture
def dq_rule() -> AlertRule:
    """Create a DQ score-based alert rule."""
    condition = AlertCondition(type=ConditionType.DQ_SCORE, params={"threshold": 0.5})
    return AlertRule(
        rule_id="dq_low",
        name="Low Data Quality Alert",
        description="Data quality score {dq_score} below threshold {threshold}",
        severity=SeverityLevel.CRITICAL,
        evaluation_stage=EvaluationStage.PROCESSED,
        source="*",  # Apply to all sources
        condition=condition,
        persistence_count=3,
        cooldown_seconds=120,
    )


@pytest.fixture
def range_rule() -> AlertRule:
    """Create a range-based alert rule."""
    return AlertRule(
        rule_id="moisture_range",
        name="Moisture Out of Range",
        description="Soil moisture outside safe range [{min_value}, {max_value}]% (actual: {value}%)",
        severity=SeverityLevel.CRITICAL,
        evaluation_stage=EvaluationStage.PROCESSED,
        source="soil_moisture",
        condition=AlertCondition(
            type=ConditionType.RANGE,
            params={"min_value": 20.0, "max_value": 80.0},
        ),
        persistence_count=3,
        cooldown_seconds=600,
    )


@pytest.fixture
def evaluator(threshold_rule) -> RuleEvaluator:
    """Create a rule evaluator with a single threshold rule."""
    return RuleEvaluator([threshold_rule])
