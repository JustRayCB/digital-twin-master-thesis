"""Tests for alert engine Kafka consumer service."""

import pytest

from dt.alerts.evaluator import RuleEvaluator
from dt.alerts.rules import AlertCondition, AlertRule, ConditionType, EvaluationStage, SeverityLevel
from dt.communication.dataclasses.alerts.alert_record import AlertStatus
from dt.communication.topics import Topics
from tests.alerts.helpers import (
    build_processed_reading,
    collect_alert_events,
    poll_alert_event,
    running_alert_service,
    wait_for_alert_state,
    wait_for_consumer_thread,
)

pytestmark = [pytest.mark.requires_kafka, pytest.mark.requires_timescale]


def test_service_subscribes_to_processed_topics_excluding_camera(
    consumer_service, registry, publisher, evaluator
):
    """Test that service subscribes to processed sensor topics except camera.

    Parameters
    ----------
    consumer_service : KafkaService
        Kafka service used for alert subscriptions.
    registry : AlertRegistry
        Registry instance for service tests.
    publisher : AlertPublisher
        Publisher emitting alert events to Kafka.
    evaluator : RuleEvaluator
        Rule evaluator for alert checks.
    Returns
    -------
    None
        The assertions raise if subscription handling regresses.
    """
    with running_alert_service(consumer_service, evaluator, registry, publisher):
        # Verify subscribe was called for each non-camera sensor topic with .processed suffix
        sensor_topics = Topics.list_sensor_topics()
        expected_topics = [
            topic.processed for topic in sensor_topics if topic != Topics.CAMERA_IMAGE
        ]

        subscribed_topics = list(consumer_service.topic_callbacks.keys())

        # Verify all non-camera processed topics were subscribed to
        for expected_topic in expected_topics:
            assert expected_topic in subscribed_topics
        assert Topics.CAMERA_IMAGE.processed not in subscribed_topics


def test_service_evaluates_payload_on_callback(
    consumer_service,
    registry,
    publisher,
    evaluator,
    alerts_consumer,
    processed_publisher,
    sample_sensor,
):
    """Test that service evaluates payload when Kafka receives a message.

    Parameters
    ----------
    consumer_service : KafkaService
        Kafka service used for alert subscriptions.
    registry : AlertRegistry
        Registry instance for service tests.
    publisher : AlertPublisher
        Publisher emitting alert events to Kafka.
    evaluator : RuleEvaluator
        Rule evaluator for alert checks.
    alerts_consumer : KafkaConsumer
        Kafka consumer subscribed to the alerts topic.
    processed_publisher : KafkaService
        Kafka service used to publish processed readings.
    sample_sensor : SensorDescriptor
        Registered sensor descriptor from the test database.
    Returns
    -------
    None
        The assertions raise if evaluation handling regresses.
    """
    with running_alert_service(consumer_service, evaluator, registry, publisher):
        reading = build_processed_reading(
            sample_sensor, value=38.0, correlation_id="svc-eval-1"
        )
        # Send two readings to satisfy persistence_count=2
        assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading)
        assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading)

        alert_event = poll_alert_event(alerts_consumer, timeout_seconds=10.0)
        assert alert_event is not None
        assert wait_for_alert_state(registry, "temp_high:temperature") is not None


def test_service_registers_candidates_with_registry(
    consumer_service,
    registry,
    publisher,
    alerts_consumer,
    processed_publisher,
    sample_sensor,
):
    """Test that service registers candidate alerts with the registry.

    Parameters
    ----------
    consumer_service : KafkaService
        Kafka service used for alert subscriptions.
    registry : AlertRegistry
        Registry instance for service tests.
    publisher : AlertPublisher
        Publisher emitting alert events to Kafka.
    alerts_consumer : KafkaConsumer
        Kafka consumer subscribed to the alerts topic.
    processed_publisher : KafkaService
        Kafka service used to publish processed readings.
    sample_sensor : SensorDescriptor
        Registered sensor descriptor from the test database.
    Returns
    -------
    None
        The assertions raise if registry registration regresses.
    """
    rule = AlertRule(
        rule_id="temp_high",
        name="High Temp",
        description="Temperature exceeds {threshold}°C",
        severity=SeverityLevel.WARNING,
        evaluation_stage=EvaluationStage.PROCESSED,
        source="temperature",
        condition=AlertCondition(
            type=ConditionType.THRESHOLD,
            params={"operator": ">", "threshold": 35.0},
        ),
        persistence_count=2,  # Set to 2 to avoid ACTIVE alert creation
        cooldown_seconds=300,
    )
    evaluator = RuleEvaluator([rule])

    with running_alert_service(consumer_service, evaluator, registry, publisher):
        # Extract and invoke callback
        reading = build_processed_reading(sample_sensor, value=38.0, correlation_id="svc-reg-1")
        assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading)

        state = wait_for_alert_state(registry, "temp_high:temperature", timeout_seconds=10.0)
        assert state is not None
        assert state.occurrences == 1
        assert poll_alert_event(alerts_consumer, timeout_seconds=2.0) is None


def test_service_publishes_created_alerts(
    consumer_service,
    registry,
    publisher,
    evaluator,
    alerts_consumer,
    processed_publisher,
    sample_sensor,
):
    """Test that service publishes ACTIVE alerts via publisher.

    Parameters
    ----------
    consumer_service : KafkaService
        Kafka service used for alert subscriptions.
    registry : AlertRegistry
        Registry instance for service tests.
    publisher : AlertPublisher
        Publisher emitting alert events to Kafka.
    evaluator : RuleEvaluator
        Rule evaluator for alert checks.
    alerts_consumer : KafkaConsumer
        Kafka consumer subscribed to the alerts topic.
    processed_publisher : KafkaService
        Kafka service used to publish processed readings.
    sample_sensor : SensorDescriptor
        Registered sensor descriptor from the test database.
    Returns
    -------
    None
        The assertions raise if publishing regresses.
    """
    with running_alert_service(consumer_service, evaluator, registry, publisher):
        # Extract and invoke callback
        reading = build_processed_reading(
            sample_sensor, value=38.0, correlation_id="svc-created-1"
        )
        # Send two readings to satisfy persistence_count=2
        assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading)
        assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading)

        event = poll_alert_event(alerts_consumer, timeout_seconds=10.0)
        assert event is not None
        assert event.status == AlertStatus.ACTIVE


def test_service_publishes_updated_alerts(
    consumer_service,
    registry,
    publisher,
    alerts_consumer,
    processed_publisher,
    sample_sensor,
):
    """Test that service publishes ACTIVE alerts via publisher.

    Parameters
    ----------
    consumer_service : KafkaService
        Kafka service used for alert subscriptions.
    registry : AlertRegistry
        Registry instance for service tests.
    publisher : AlertPublisher
        Publisher emitting alert events to Kafka.
    evaluator : RuleEvaluator
        Rule evaluator for alert checks.
    alerts_consumer : KafkaConsumer
        Kafka consumer subscribed to the alerts topic.
    processed_publisher : KafkaService
        Kafka service used to publish processed readings.
    sample_sensor : SensorDescriptor
        Registered sensor descriptor from the test database.
    Returns
    -------
    None
        The assertions raise if updates stop publishing.
    """
    rule = AlertRule(
        rule_id="temp_high",
        name="High Temp",
        description="Temperature exceeds {threshold}°C",
        severity=SeverityLevel.WARNING,
        evaluation_stage=EvaluationStage.PROCESSED,
        source="temperature",
        condition=AlertCondition(
            type=ConditionType.THRESHOLD,
            params={"operator": ">", "threshold": 35.0},
        ),
        persistence_count=1,
        cooldown_seconds=0,
    )
    evaluator = RuleEvaluator([rule])

    with running_alert_service(consumer_service, evaluator, registry, publisher):
        # Extract and invoke callback
        reading = build_processed_reading(
            sample_sensor, value=38.0, correlation_id="svc-updated-1"
        )
        assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading)
        assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading)

        events = collect_alert_events(alerts_consumer, count=2, timeout_seconds=10.0)
        assert len(events) == 2


def test_service_does_not_publish_ignored_alerts(
    consumer_service,
    registry,
    publisher,
    alerts_consumer,
    processed_publisher,
    sample_sensor,
):
    """Test that service does not publish IGNORED alerts.

    Parameters
    ----------
    consumer_service : KafkaService
        Kafka service used for alert subscriptions.
    registry : AlertRegistry
        Registry instance for service tests.
    publisher : AlertPublisher
        Publisher emitting alert events to Kafka.
    evaluator : RuleEvaluator
        Rule evaluator for alert checks.
    alerts_consumer : KafkaConsumer
        Kafka consumer subscribed to the alerts topic.
    processed_publisher : KafkaService
        Kafka service used to publish processed readings.
    sample_sensor : SensorDescriptor
        Registered sensor descriptor from the test database.
    Returns
    -------
    None
        The assertions raise if ignored alerts are published.
    """
    rule = AlertRule(
        rule_id="temp_high",
        name="High Temp",
        description="Temperature exceeds {threshold}°C",
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
    evaluator = RuleEvaluator([rule])

    with running_alert_service(consumer_service, evaluator, registry, publisher):
        # Extract and invoke callback
        reading = build_processed_reading(
            sample_sensor, value=38.0, correlation_id="svc-ignored-1"
        )
        assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading)

        assert poll_alert_event(alerts_consumer, timeout_seconds=2.0) is None
        assert registry._states != {}


def test_service_handles_multiple_candidates(
    consumer_service,
    registry,
    publisher,
    alerts_consumer,
    processed_publisher,
    sample_sensor,
):
    """Test that service handles multiple candidate alerts from one payload.

    Parameters
    ----------
    consumer_service : KafkaService
        Kafka service used for alert subscriptions.
    registry : AlertRegistry
        Registry instance for service tests.
    publisher : AlertPublisher
        Publisher emitting alert events to Kafka.
    alerts_consumer : KafkaConsumer
        Kafka consumer subscribed to the alerts topic.
    processed_publisher : KafkaService
        Kafka service used to publish processed readings.
    sample_sensor : SensorDescriptor
        Registered sensor descriptor from the test database.
    Returns
    -------
    None
        The assertions raise if multi-rule handling regresses.
    """
    threshold_rule = AlertRule(
        rule_id="temp_high",
        name="High Temp",
        description="Temperature exceeds {threshold}°C",
        severity=SeverityLevel.WARNING,
        evaluation_stage=EvaluationStage.PROCESSED,
        source="temperature",
        condition=AlertCondition(
            type=ConditionType.THRESHOLD,
            params={"operator": ">", "threshold": 35.0},
        ),
        persistence_count=1,
        cooldown_seconds=300,
    )
    dq_rule = AlertRule(
        rule_id="dq_low",
        name="DQ Low",
        description="Data quality below threshold",
        severity=SeverityLevel.INFO,
        evaluation_stage=EvaluationStage.PROCESSED,
        source="temperature",
        condition=AlertCondition(type=ConditionType.DQ_SCORE, params={"threshold": 0.99}),
        persistence_count=1,
        cooldown_seconds=300,
    )
    evaluator = RuleEvaluator([threshold_rule, dq_rule])

    with running_alert_service(consumer_service, evaluator, registry, publisher):
        # Extract and invoke callback
        reading = build_processed_reading(
            sample_sensor, value=38.0, correlation_id="svc-multi-1"
        )
        reading.dq_score = 0.5
        assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading)

        events = collect_alert_events(alerts_consumer, count=2, timeout_seconds=10.0)
        assert {event.alert_key for event in events} == {
            "temp_high:temperature",
            "dq_low:temperature",
        }


def test_service_shutdown(consumer_service, registry, publisher, evaluator):
    """Test that service can be gracefully shut down.

    Parameters
    ----------
    consumer_service : KafkaService
        Kafka service used for alert subscriptions.
    registry : AlertRegistry
        Registry instance for service tests.
    publisher : AlertPublisher
        Publisher emitting alert events to Kafka.
    evaluator : RuleEvaluator
        Rule evaluator for alert checks.
    Returns
    -------
    None
        The assertions raise if shutdown handling regresses.
    """
    from dt.alerts.service import AlertEngineService

    service = AlertEngineService(
        kafka_service=consumer_service,
        evaluator=evaluator,
        registry=registry,
        publisher=publisher,
    )

    service.start()
    # Wait for start before shutdown to be clean
    wait_for_consumer_thread(consumer_service)
    service.shutdown()

    assert consumer_service._running is False


def test_service_does_not_fail_when_no_candidates(
    consumer_service,
    registry,
    publisher,
    alerts_consumer,
    processed_publisher,
    sample_sensor,
):
    """Test that service handles payloads that produce no candidate alerts.

    Parameters
    ----------
    consumer_service : KafkaService
        Kafka service used for alert subscriptions.
    registry : AlertRegistry
        Registry instance for service tests.
    publisher : AlertPublisher
        Publisher emitting alert events to Kafka.
    alerts_consumer : KafkaConsumer
        Kafka consumer subscribed to the alerts topic.
    processed_publisher : KafkaService
        Kafka service used to publish processed readings.
    sample_sensor : SensorDescriptor
        Registered sensor descriptor from the test database.
    Returns
    -------
    None
        The assertions raise if empty evaluations regress.
    """
    evaluator = RuleEvaluator([])
    with running_alert_service(consumer_service, evaluator, registry, publisher):
        reading = build_processed_reading(sample_sensor, value=38.0, correlation_id="svc-empty-1")
        assert processed_publisher.publish(Topics.TEMPERATURE.processed, reading)
        import time
        time.sleep(0.5)

        assert poll_alert_event(alerts_consumer, timeout_seconds=2.0) is None
        assert registry._states == {}
