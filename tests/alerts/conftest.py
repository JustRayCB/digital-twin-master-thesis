"""Shared fixtures for alert engine tests."""

from __future__ import annotations

import uuid

import pytest

from dt.analytics.alerts.evaluator import RuleEvaluator
from dt.analytics.alerts.publisher import AlertPublisher
from dt.analytics.alerts.registry import AlertRegistry
from dt.analytics.alerts.rules import (AlertCondition, AlertRule, ConditionType,
                             EvaluationStage, SeverityLevel)
from dt.communication.dataclasses import ProcessedSensorData, SensorDescriptor
from dt.communication.dataclasses.alerts.alert_record import (
    AlertDefinition, AlertStatus, SensorAlertEvent)
from dt.communication.dataclasses.alerts.alert_type import AlertType
from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.messaging_service import KafkaService
from dt.communication.topics import Topics
from tests.helpers import create_topic_consumer


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
    consumer = create_topic_consumer(
        Topics.ALERTS,
        kafka_bootstrap_servers,
        group_prefix="alert-tests",
    )
    yield consumer
    consumer.close()


@pytest.fixture(scope="module")
def sample_plant_id(shared_metadata_store) -> int:
    """Create a sample plant in the test database.

    Parameters
    ----------
    shared_metadata_store : MetadataStore
        Metadata store backed by the test database.

    Returns
    -------
    int
        Plant identifier for alert tests.
    """
    return shared_metadata_store.upsert_plant(
        name="Alert Test Plant", notes="Alert service tests"
    )


@pytest.fixture(scope="module")
def sample_sensor(shared_metadata_store, sample_plant_id) -> SensorDescriptor:
    """Create a sample sensor in the test database.

    Parameters
    ----------
    shared_metadata_store : MetadataStore
        Metadata store backed by the test database.
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
    sensor_id = shared_metadata_store.register_sensor(sensor)
    sensor.id = sensor_id
    return sensor


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
def publisher(kafka_service, database_api_client) -> AlertPublisher:
    """Create an alert publisher backed by Kafka and the database service."""
    return AlertPublisher(kafka_service, definition_client=database_api_client)


@pytest.fixture
def consumer_service(kafka_bootstrap_servers, kafka_topics):
    """Create a KafkaService for consuming processed sensor data."""
    client_id = f"alert-consumer-{uuid.uuid4().hex[:8]}"
    return KafkaService(host=kafka_bootstrap_servers, client_id=client_id, group_id=client_id)


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
