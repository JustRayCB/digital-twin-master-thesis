"""Integration tests for the database messaging bridge."""

import time
from collections.abc import Callable

import pytest

from dt.alerts.rules import SeverityLevel
from dt.communication.dataclasses import ProcessedSensorData
from dt.communication.dataclasses.alerts.alert_record import (
    AlertDefinition,
    AlertStatus,
    ExternalAlertEvent,
    SensorAlertEvent,
)
from dt.communication.dataclasses.alerts.alert_type import AlertType
from dt.communication.dataclasses.queries import AlertHistoryQuery, ReadingsQuery
from dt.communication.messaging_service import KafkaService
from dt.communication.topics import Topics
from dt.data.database.consumer import setup_bridge
from dt.data.database.timescale_storage import TimescaleStorage

pytestmark = [pytest.mark.requires_kafka, pytest.mark.requires_timescale]


def wait_for_kafka_service_ready(
    bridge: KafkaService, wait_until_condition: Callable[..., None], expected_topics: set[str]
) -> None:
    """Wait until the KafkaService consumer has joined and subscribed.

    Parameters
    ----------
    bridge : KafkaService
        Service returned by the database bridge setup.
    wait_until_condition : Callable[..., None]
        Polling helper from fixtures.
    expected_topics : set[str]
        Topics expected to be in the consumer subscription.

    Returns
    -------
    None
        Raises on timeout.
    """

    def is_ready() -> bool:
        if bridge.consumer is None:
            return False
        subscription = bridge.consumer.subscription()
        if not expected_topics.issubset(subscription):
            return False
        return bool(bridge.consumer.assignment())

    wait_until_condition(is_ready, timeout_seconds=15.0, interval_seconds=0.25)


def test_bridge_persists_processed_reading(
    kafka_bootstrap_servers: str,
    kafka_service: KafkaService,
    storage: TimescaleStorage,
    sample_sensor,
    wait_until_condition: Callable[..., None],
) -> None:
    """Persist processed readings received from Kafka.

    Parameters
    ----------
    kafka_bootstrap_servers : str
        Kafka bootstrap servers for the test broker.
    kafka_service : KafkaService
        Producer service for publishing processed readings.
    storage : TimescaleStorage
        Storage instance used by the bridge.
    sample_sensor : dt.communication.dataclasses.SensorDescriptor
        Registered sensor descriptor.
    wait_until_condition : Callable[..., None]
        Polling helper for async conditions.

    Returns
    -------
    None
        The assertions raise if bridge persistence regresses.
    """
    test_config = type("TestConfig", (), {"KAFKA_URL": kafka_bootstrap_servers})
    bridge = setup_bridge(config=test_config, storage=storage)
    assert isinstance(bridge, KafkaService)

    try:
        wait_for_kafka_service_ready(
            bridge,
            wait_until_condition,
            expected_topics={Topics.TEMPERATURE.processed, Topics.ALERTS},
        )

        test_reading = ProcessedSensorData(
            plant_id=sample_sensor.plant_id,
            sensor_id=sample_sensor.id,
            timestamp=time.time(),
            value=23.5,
            unit="°C",
            topic=Topics.TEMPERATURE,
            correlation_id="kafka-integration-test",
            flags={},
            dq_score=0.99,
            imputed=False,
        )
        kafka_service.publish(Topics.TEMPERATURE.processed, test_reading)

        def reading_persisted() -> bool:
            readings = storage.query_readings(
                ReadingsQuery(sensor_id=sample_sensor.id, since=test_reading.timestamp - 60)
            )
            return any(reading.correlation_id == "kafka-integration-test" for reading in readings)

        wait_until_condition(reading_persisted, timeout_seconds=10.0, interval_seconds=0.25)

    finally:
        bridge.disconnect()


def test_bridge_persists_multiple_processed_readings(
    kafka_bootstrap_servers: str,
    kafka_service: KafkaService,
    storage: TimescaleStorage,
    sample_sensor,
    wait_until_condition: Callable[..., None],
) -> None:
    """Persist multiple processed readings received from Kafka.

    Parameters
    ----------
    kafka_bootstrap_servers : str
        Kafka bootstrap servers for the test broker.
    kafka_service : KafkaService
        Producer service for publishing processed readings.
    storage : TimescaleStorage
        Storage instance used by the bridge.
    sample_sensor : dt.communication.dataclasses.SensorDescriptor
        Registered sensor descriptor.
    wait_until_condition : Callable[..., None]
        Polling helper for async conditions.

    Returns
    -------
    None
        The assertions raise if multi-message ingestion regresses.
    """
    test_config = type("TestConfig", (), {"KAFKA_URL": kafka_bootstrap_servers})
    bridge = setup_bridge(config=test_config, storage=storage)
    assert isinstance(bridge, KafkaService)

    try:
        wait_for_kafka_service_ready(
            bridge,
            wait_until_condition,
            expected_topics={Topics.TEMPERATURE.processed, Topics.ALERTS},
        )

        base_time = time.time()
        for i in range(3):
            kafka_service.publish(
                Topics.TEMPERATURE.processed,
                ProcessedSensorData(
                    plant_id=sample_sensor.plant_id,
                    sensor_id=sample_sensor.id,
                    timestamp=base_time + i,
                    value=20.0 + i,
                    unit="°C",
                    topic=Topics.TEMPERATURE,
                    correlation_id=f"multi-test-{i}",
                    flags={},
                    dq_score=0.99,
                    imputed=False,
                ),
            )

        def readings_persisted() -> bool:
            readings = storage.query_readings(
                ReadingsQuery(sensor_id=sample_sensor.id, since=base_time - 60)
            )
            recent = {reading.correlation_id for reading in readings}
            return {"multi-test-0", "multi-test-1", "multi-test-2"}.issubset(recent)

        wait_until_condition(readings_persisted, timeout_seconds=12.0, interval_seconds=0.25)

    finally:
        bridge.disconnect()


def test_bridge_persists_sensor_alert_event(
    kafka_bootstrap_servers: str,
    kafka_service: KafkaService,
    storage: TimescaleStorage,
    sample_sensor,
    wait_until_condition: Callable[..., None],
) -> None:
    """Persist sensor alert events received from Kafka.

    Parameters
    ----------
    kafka_bootstrap_servers : str
        Kafka bootstrap servers for the test broker.
    kafka_service : KafkaService
        Producer service for publishing alert events.
    storage : TimescaleStorage
        Storage instance used by the bridge.
    sample_sensor : dt.communication.dataclasses.SensorDescriptor
        Registered sensor descriptor.
    wait_until_condition : Callable[..., None]
        Polling helper for async conditions.

    Returns
    -------
    None
        The assertions raise if alert event persistence regresses.
    """
    alert_key = "high_temp:sensor_test"
    storage.save_alert_definition(
        AlertDefinition(
            alert_key=alert_key,
            plant_id=sample_sensor.plant_id,
            sensor_id=sample_sensor.id,
            source="sensor_rule",
            rule_id="rule_1",
            rule_name="High Temperature",
            kind=AlertType.SENSOR,
            persistence_count=1,
            cooldown_seconds=300,
        )
    )

    test_config = type("TestConfig", (), {"KAFKA_URL": kafka_bootstrap_servers})
    bridge = setup_bridge(config=test_config, storage=storage)
    assert isinstance(bridge, KafkaService)

    try:
        wait_for_kafka_service_ready(bridge, wait_until_condition, {Topics.ALERTS})

        test_timestamp = time.time()
        kafka_service.publish(
            Topics.ALERTS,
            SensorAlertEvent(
                alert_key=alert_key,
                plant_id=sample_sensor.plant_id,
                timestamp=test_timestamp,
                status=AlertStatus.ACTIVE,
                severity=SeverityLevel.WARNING,
                message="Temperature exceeded 30°C threshold",
                correlation_id="alert-integration-test-1",
                reading=ProcessedSensorData(
                    plant_id=sample_sensor.plant_id,
                    sensor_id=sample_sensor.id,
                    timestamp=test_timestamp,
                    value=32.5,
                    unit="°C",
                    topic=Topics.TEMPERATURE,
                    correlation_id="alert-integration-test-1",
                    flags={},
                    dq_score=1.0,
                    imputed=False,
                ),
                threshold_op=">",
                threshold_value=30.0,
            ),
        )

        def event_persisted() -> bool:
            history = storage.get_alert_history(
                AlertHistoryQuery(plant_id=sample_sensor.plant_id, limit=20)
            )
            return any(event.correlation_id == "alert-integration-test-1" for event in history)

        wait_until_condition(event_persisted, timeout_seconds=10.0, interval_seconds=0.25)

    finally:
        bridge.disconnect()


def test_bridge_persists_external_alert_event(
    kafka_bootstrap_servers: str,
    kafka_service: KafkaService,
    storage: TimescaleStorage,
    sample_sensor,
    wait_until_condition: Callable[..., None],
) -> None:
    """Persist external alert events received from Kafka.

    Parameters
    ----------
    kafka_bootstrap_servers : str
        Kafka bootstrap servers for the test broker.
    kafka_service : KafkaService
        Producer service for publishing alert events.
    storage : TimescaleStorage
        Storage instance used by the bridge.
    sample_sensor : dt.communication.dataclasses.SensorDescriptor
        Registered sensor descriptor.
    wait_until_condition : Callable[..., None]
        Polling helper for async conditions.

    Returns
    -------
    None
        The assertions raise if external alert persistence regresses.
    """
    alert_key = "ai_anomaly:plant_test"
    storage.save_alert_definition(
        AlertDefinition(
            alert_key=alert_key,
            plant_id=sample_sensor.plant_id,
            sensor_id=None,
            source="external_ai",
            rule_id=None,
            rule_name=None,
            kind=AlertType.EXTERNAL,
            persistence_count=1,
            cooldown_seconds=300,
        )
    )

    test_config = type("TestConfig", (), {"KAFKA_URL": kafka_bootstrap_servers})
    bridge = setup_bridge(config=test_config, storage=storage)
    assert isinstance(bridge, KafkaService)

    try:
        wait_for_kafka_service_ready(bridge, wait_until_condition, {Topics.ALERTS})

        kafka_service.publish(
            Topics.ALERTS,
            ExternalAlertEvent(
                alert_key=alert_key,
                plant_id=sample_sensor.plant_id,
                timestamp=time.time(),
                status=AlertStatus.ACTIVE,
                severity=SeverityLevel.CRITICAL,
                message="AI detected anomalous growth pattern",
                correlation_id="alert-integration-test-2",
                metadata={"model_version": "v1.2", "confidence": "0.95"},
            ),
        )

        def event_persisted() -> bool:
            history = storage.get_alert_history(
                AlertHistoryQuery(plant_id=sample_sensor.plant_id, limit=20)
            )
            return any(event.correlation_id == "alert-integration-test-2" for event in history)

        wait_until_condition(event_persisted, timeout_seconds=10.0, interval_seconds=0.25)

    finally:
        bridge.disconnect()
