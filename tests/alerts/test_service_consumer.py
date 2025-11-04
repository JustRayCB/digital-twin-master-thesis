"""Tests for alert engine Kafka consumer service."""

from unittest.mock import Mock, call

import pytest

from dt.alerts.config.alert_rule import (AlertCondition, AlertRule,
                                         ConditionType, EvaluationStage,
                                         SeverityLevel)
from dt.alerts.state.models import AlertLifecycleEvent
from dt.communication import Topics
from dt.communication.dataclasses import ProcessedSensorData
from dt.communication.dataclasses.processed_sensor_data import ValidationFlag
from dt.communication.dataclasses.alerts import CandidateAlert


@pytest.fixture
def mock_kafka_service():
    """Create a mock KafkaService."""
    mock = Mock()
    mock.subscribe = Mock(return_value=True)
    mock.connect = Mock(return_value=True)
    mock.disconnect = Mock()
    return mock


@pytest.fixture
def mock_registry():
    """Create a mock AlertRegistry."""
    mock = Mock()
    mock.register = Mock(return_value=AlertLifecycleEvent.CREATED)
    return mock


@pytest.fixture
def mock_publisher():
    """Create a mock AlertPublisher."""
    mock = Mock()
    mock.publish = Mock(return_value=True)
    return mock


@pytest.fixture
def mock_evaluator():
    """Create a mock RuleEvaluator."""
    mock = Mock()
    mock.evaluate = Mock(return_value=[])
    return mock


@pytest.fixture
def sample_processed_data():
    """Create sample processed sensor data."""
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


def test_service_subscribes_to_all_processed_topics(
    mock_kafka_service, mock_registry, mock_publisher, mock_evaluator
):
    """Test that service subscribes to all processed sensor topics."""
    from dt.alerts.service import AlertEngineService

    service = AlertEngineService(
        kafka_service=mock_kafka_service,
        evaluator=mock_evaluator,
        registry=mock_registry,
        publisher=mock_publisher,
    )

    service.start()

    # Verify subscribe was called for each sensor topic with .processed suffix
    sensor_topics = Topics.list_sensor_topics()
    expected_topics = [topic.processed for topic in sensor_topics]

    # Should be called once per processed topic
    assert mock_kafka_service.subscribe.call_count == len(expected_topics)

    # Extract the topics from subscribe calls
    subscribe_calls = mock_kafka_service.subscribe.call_args_list
    subscribed_topics = [call_args[0][0] for call_args in subscribe_calls]

    # Verify all processed topics were subscribed to
    for expected_topic in expected_topics:
        assert expected_topic in subscribed_topics


def test_service_evaluates_payload_on_callback(
    mock_kafka_service, mock_registry, mock_publisher, mock_evaluator, sample_processed_data
):
    """Test that service evaluates payload when callback is invoked."""
    from dt.alerts.service import AlertEngineService

    service = AlertEngineService(
        kafka_service=mock_kafka_service,
        evaluator=mock_evaluator,
        registry=mock_registry,
        publisher=mock_publisher,
    )

    service.start()

    # Extract the callback from the first subscribe call
    first_subscribe_call = mock_kafka_service.subscribe.call_args_list[0]
    callback = first_subscribe_call[0][1]

    # Invoke the callback with sample data
    callback(sample_processed_data)

    # Verify evaluator was called with the payload
    mock_evaluator.evaluate.assert_called_once_with(sample_processed_data)


def test_service_registers_candidates_with_registry(
    mock_kafka_service, mock_registry, mock_publisher, mock_evaluator, sample_processed_data
):
    """Test that service registers candidate alerts with the registry."""
    from dt.alerts.service import AlertEngineService

    # Create a sample candidate alert
    candidate = CandidateAlert(
        alert_id="temp_high:temperature",
        rule_id="temp_high",
        source="temperature",
        severity=SeverityLevel.WARNING,
        message="Temperature exceeds 35°C",
        correlation_id=sample_processed_data.correlation_id,
        payload=sample_processed_data.to_dict(),
        persistence_count=1,
        cooldown_seconds=300,
    )

    # Configure evaluator to return the candidate
    mock_evaluator.evaluate = Mock(return_value=[candidate])

    service = AlertEngineService(
        kafka_service=mock_kafka_service,
        evaluator=mock_evaluator,
        registry=mock_registry,
        publisher=mock_publisher,
    )

    service.start()

    # Extract and invoke callback
    callback = mock_kafka_service.subscribe.call_args_list[0][0][1]
    callback(sample_processed_data)

    # Verify registry.register was called with the candidate
    mock_registry.register.assert_called_once()
    call_args = mock_registry.register.call_args
    assert call_args[0][0] == candidate


def test_service_publishes_created_alerts(
    mock_kafka_service, mock_registry, mock_publisher, mock_evaluator, sample_processed_data
):
    """Test that service publishes CREATED alerts via publisher."""
    from dt.alerts.service import AlertEngineService

    candidate = CandidateAlert(
        alert_id="temp_high:temperature",
        rule_id="temp_high",
        source="temperature",
        severity=SeverityLevel.WARNING,
        message="Temperature exceeds 35°C",
        correlation_id=sample_processed_data.correlation_id,
        payload=sample_processed_data.to_dict(),
        persistence_count=1,
        cooldown_seconds=300,
    )

    mock_evaluator.evaluate = Mock(return_value=[candidate])
    mock_registry.register = Mock(return_value=AlertLifecycleEvent.CREATED)

    service = AlertEngineService(
        kafka_service=mock_kafka_service,
        evaluator=mock_evaluator,
        registry=mock_registry,
        publisher=mock_publisher,
    )

    service.start()

    # Extract and invoke callback
    callback = mock_kafka_service.subscribe.call_args_list[0][0][1]
    callback(sample_processed_data)

    # Verify publisher was called for CREATED event
    mock_publisher.publish.assert_called_once_with(AlertLifecycleEvent.CREATED, candidate)


def test_service_publishes_updated_alerts(
    mock_kafka_service, mock_registry, mock_publisher, mock_evaluator, sample_processed_data
):
    """Test that service publishes UPDATED alerts via publisher."""
    from dt.alerts.service import AlertEngineService

    candidate = CandidateAlert(
        alert_id="temp_high:temperature",
        rule_id="temp_high",
        source="temperature",
        severity=SeverityLevel.WARNING,
        message="Temperature exceeds 35°C",
        correlation_id=sample_processed_data.correlation_id,
        payload=sample_processed_data.to_dict(),
        persistence_count=1,
        cooldown_seconds=300,
    )

    mock_evaluator.evaluate = Mock(return_value=[candidate])
    mock_registry.register = Mock(return_value=AlertLifecycleEvent.UPDATED)

    service = AlertEngineService(
        kafka_service=mock_kafka_service,
        evaluator=mock_evaluator,
        registry=mock_registry,
        publisher=mock_publisher,
    )

    service.start()

    # Extract and invoke callback
    callback = mock_kafka_service.subscribe.call_args_list[0][0][1]
    callback(sample_processed_data)

    # Verify publisher was called for UPDATED event
    mock_publisher.publish.assert_called_once_with(AlertLifecycleEvent.UPDATED, candidate)


def test_service_does_not_publish_ignored_alerts(
    mock_kafka_service, mock_registry, mock_publisher, mock_evaluator, sample_processed_data
):
    """Test that service does not publish IGNORED alerts."""
    from dt.alerts.service import AlertEngineService

    candidate = CandidateAlert(
        alert_id="temp_high:temperature",
        rule_id="temp_high",
        source="temperature",
        severity=SeverityLevel.WARNING,
        message="Temperature exceeds 35°C",
        correlation_id=sample_processed_data.correlation_id,
        payload=sample_processed_data.to_dict(),
        persistence_count=1,
        cooldown_seconds=300,
    )

    mock_evaluator.evaluate = Mock(return_value=[candidate])
    mock_registry.register = Mock(return_value=AlertLifecycleEvent.IGNORED)

    service = AlertEngineService(
        kafka_service=mock_kafka_service,
        evaluator=mock_evaluator,
        registry=mock_registry,
        publisher=mock_publisher,
    )

    service.start()

    # Extract and invoke callback
    callback = mock_kafka_service.subscribe.call_args_list[0][0][1]
    callback(sample_processed_data)

    # Verify publisher was NOT called for IGNORED event
    mock_publisher.publish.assert_not_called()


def test_service_does_not_publish_suppressed_alerts(
    mock_kafka_service, mock_registry, mock_publisher, mock_evaluator, sample_processed_data
):
    """Test that service does not publish SUPPRESSED alerts."""
    from dt.alerts.service import AlertEngineService

    candidate = CandidateAlert(
        alert_id="temp_high:temperature",
        rule_id="temp_high",
        source="temperature",
        severity=SeverityLevel.WARNING,
        message="Temperature exceeds 35°C",
        correlation_id=sample_processed_data.correlation_id,
        payload=sample_processed_data.to_dict(),
        persistence_count=1,
        cooldown_seconds=300,
    )

    mock_evaluator.evaluate = Mock(return_value=[candidate])
    mock_registry.register = Mock(return_value=AlertLifecycleEvent.SUPPRESSED)

    service = AlertEngineService(
        kafka_service=mock_kafka_service,
        evaluator=mock_evaluator,
        registry=mock_registry,
        publisher=mock_publisher,
    )

    service.start()

    # Extract and invoke callback
    callback = mock_kafka_service.subscribe.call_args_list[0][0][1]
    callback(sample_processed_data)

    # Verify publisher was NOT called for SUPPRESSED event
    mock_publisher.publish.assert_not_called()


def test_service_handles_multiple_candidates(
    mock_kafka_service, mock_registry, mock_publisher, mock_evaluator, sample_processed_data
):
    """Test that service handles multiple candidate alerts from one payload."""
    from dt.alerts.service import AlertEngineService

    candidate1 = CandidateAlert(
        alert_id="temp_high:temperature",
        rule_id="temp_high",
        source="temperature",
        severity=SeverityLevel.WARNING,
        message="Temperature exceeds 35°C",
        correlation_id=sample_processed_data.correlation_id,
        payload=sample_processed_data.to_dict(),
        persistence_count=1,
        cooldown_seconds=300,
    )

    candidate2 = CandidateAlert(
        alert_id="dq_low:temperature",
        rule_id="dq_low",
        source="temperature",
        severity=SeverityLevel.INFO,
        message="Data quality below threshold",
        correlation_id=sample_processed_data.correlation_id,
        payload=sample_processed_data.to_dict(),
        persistence_count=1,
        cooldown_seconds=300,
    )

    # Return two candidates
    mock_evaluator.evaluate = Mock(return_value=[candidate1, candidate2])
    mock_registry.register = Mock(return_value=AlertLifecycleEvent.CREATED)

    service = AlertEngineService(
        kafka_service=mock_kafka_service,
        evaluator=mock_evaluator,
        registry=mock_registry,
        publisher=mock_publisher,
    )

    service.start()

    # Extract and invoke callback
    callback = mock_kafka_service.subscribe.call_args_list[0][0][1]
    callback(sample_processed_data)

    # Verify both candidates were registered
    assert mock_registry.register.call_count == 2

    # Verify both candidates were published
    assert mock_publisher.publish.call_count == 2


def test_service_shutdown(mock_kafka_service, mock_registry, mock_publisher, mock_evaluator):
    """Test that service can be gracefully shut down."""
    from dt.alerts.service import AlertEngineService

    service = AlertEngineService(
        kafka_service=mock_kafka_service,
        evaluator=mock_evaluator,
        registry=mock_registry,
        publisher=mock_publisher,
    )

    service.start()
    service.shutdown()

    # Verify disconnect was called on kafka service
    mock_kafka_service.disconnect.assert_called_once()


def test_service_does_not_fail_when_no_candidates(
    mock_kafka_service, mock_registry, mock_publisher, mock_evaluator, sample_processed_data
):
    """Test that service handles payloads that produce no candidate alerts."""
    from dt.alerts.service import AlertEngineService

    # Evaluator returns empty list (no rules triggered)
    mock_evaluator.evaluate = Mock(return_value=[])

    service = AlertEngineService(
        kafka_service=mock_kafka_service,
        evaluator=mock_evaluator,
        registry=mock_registry,
        publisher=mock_publisher,
    )

    service.start()

    # Extract and invoke callback
    callback = mock_kafka_service.subscribe.call_args_list[0][0][1]
    callback(sample_processed_data)

    # Verify registry and publisher were not called
    mock_registry.register.assert_not_called()
    mock_publisher.publish.assert_not_called()
