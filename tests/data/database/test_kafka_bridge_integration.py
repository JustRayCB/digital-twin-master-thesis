"""Integration tests for the database messaging bridge."""

import time

import pytest

from dt.analytics.alerts.rules import SeverityLevel
from dt.communication.dataclasses.analytics import (
    ActionResult,
    ForecastResult,
    HealthAssessment,
    HealthState,
    Recommendation,
    RecommendedAction,
    ModelMetadata,
)
from dt.communication.dataclasses import CameraSnapshot, ProcessedSensorData
from dt.communication.dataclasses.alerts.alert_record import (
    AlertDefinition, AlertStatus, ExternalAlertEvent, SensorAlertEvent)
from dt.communication.dataclasses.alerts.alert_type import AlertType
from dt.communication.dataclasses.controller import ActionCommand
from dt.communication.dataclasses.queries import (ActionHistoryQuery,
                                                   AlertHistoryQuery,
                                                   ForecastHistoryQuery,
                                                   HealthHistoryQuery,
                                                   RecommendationHistoryQuery,
                                                   ReadingsQuery)
from dt.communication.messaging_service import KafkaService
from dt.communication.topics import Topics
from dt.data.database import AnalyticsStore
from dt.data.database.consumer import setup_bridge
from tests.data.database.helpers import (wait_for_kafka_service_ready,
                                          wait_until)

pytestmark = [pytest.mark.requires_kafka, pytest.mark.requires_timescale]


def test_bridge_persists_processed_reading(
    kafka_bootstrap_servers: str,
    kafka_service: KafkaService,
    analytics_store: AnalyticsStore,
    readings_store,
    alert_store,
    controller_store,
    snapshot_store,
    sample_sensor,
) -> None:
    """Persist processed readings received from Kafka.

    Parameters
    ----------
    kafka_bootstrap_servers : str
        Kafka bootstrap servers for the test broker.
    kafka_service : KafkaService
        Producer service for publishing processed readings.
    readings_store, alert_store, controller_store, snapshot_store
        Dedicated stores used by the bridge.
    sample_sensor : dt.communication.dataclasses.SensorDescriptor
        Registered sensor descriptor.
    """
    test_config = type("TestConfig", (), {"KAFKA_URL": kafka_bootstrap_servers})
    bridge = setup_bridge(
        config=test_config,
        readings_storage=readings_store,
        alert_storage=alert_store,
        analytics_storage=analytics_store,
        controller_storage=controller_store,
        snapshot_storage=snapshot_store,
    )
    assert isinstance(bridge, KafkaService)

    try:
        wait_for_kafka_service_ready(
            bridge, expected_topics={Topics.TEMPERATURE.processed, Topics.ALERTS}
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
            readings = readings_store.query_readings(
                ReadingsQuery(sensor_id=sample_sensor.id, since=test_reading.timestamp - 60)
            )
            return any(reading.correlation_id == "kafka-integration-test" for reading in readings)

        wait_until(reading_persisted, timeout_seconds=10.0, interval_seconds=0.25)

    finally:
        bridge.disconnect()


def test_bridge_persists_multiple_processed_readings(
    kafka_bootstrap_servers: str,
    kafka_service: KafkaService,
    analytics_store: AnalyticsStore,
    readings_store,
    alert_store,
    controller_store,
    snapshot_store,
    sample_sensor,
) -> None:
    """Persist multiple processed readings received from Kafka.

    Parameters
    ----------
    kafka_bootstrap_servers : str
        Kafka bootstrap servers for the test broker.
    kafka_service : KafkaService
        Producer service for publishing processed readings.
    readings_store, alert_store, controller_store, snapshot_store
        Dedicated stores used by the bridge.
    sample_sensor : dt.communication.dataclasses.SensorDescriptor
        Registered sensor descriptor.
    """
    test_config = type("TestConfig", (), {"KAFKA_URL": kafka_bootstrap_servers})
    bridge = setup_bridge(
        config=test_config,
        readings_storage=readings_store,
        alert_storage=alert_store,
        analytics_storage=analytics_store,
        controller_storage=controller_store,
        snapshot_storage=snapshot_store,
    )
    assert isinstance(bridge, KafkaService)

    try:
        wait_for_kafka_service_ready(
            bridge, expected_topics={Topics.TEMPERATURE.processed, Topics.ALERTS}
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
            readings = readings_store.query_readings(
                ReadingsQuery(sensor_id=sample_sensor.id, since=base_time - 60)
            )
            recent = {reading.correlation_id for reading in readings}
            return {"multi-test-0", "multi-test-1", "multi-test-2"}.issubset(recent)

        wait_until(readings_persisted, timeout_seconds=12.0, interval_seconds=0.25)

    finally:
        bridge.disconnect()


def test_bridge_persists_processed_green_ratio_reading(
    kafka_bootstrap_servers: str,
    kafka_service: KafkaService,
    analytics_store: AnalyticsStore,
    readings_store,
    alert_store,
    controller_store,
    snapshot_store,
    sample_sensor,
) -> None:
    """Persist processed green-ratio readings received from Kafka."""
    test_config = type("TestConfig", (), {"KAFKA_URL": kafka_bootstrap_servers})
    bridge = setup_bridge(
        config=test_config,
        readings_storage=readings_store,
        alert_storage=alert_store,
        analytics_storage=analytics_store,
        controller_storage=controller_store,
        snapshot_storage=snapshot_store,
    )
    assert isinstance(bridge, KafkaService)

    try:
        wait_for_kafka_service_ready(
            bridge, expected_topics={Topics.GREEN_RATIO.processed, Topics.ALERTS}
        )

        test_reading = ProcessedSensorData(
            plant_id=sample_sensor.plant_id,
            sensor_id=sample_sensor.id,
            timestamp=time.time(),
            value=0.42,
            unit="ratio",
            topic=Topics.GREEN_RATIO,
            correlation_id="green-ratio-kafka-integration-test",
            flags={},
            dq_score=0.98,
            imputed=False,
        )
        kafka_service.publish(Topics.GREEN_RATIO.processed, test_reading)

        def green_ratio_reading_persisted() -> bool:
            readings = readings_store.query_readings(
                ReadingsQuery(
                    sensor_id=sample_sensor.id,
                    topic=Topics.GREEN_RATIO,
                    since=test_reading.timestamp - 60,
                )
            )
            return any(
                reading.correlation_id == "green-ratio-kafka-integration-test" for reading in readings
            )

        wait_until(green_ratio_reading_persisted, timeout_seconds=10.0, interval_seconds=0.25)

        persisted_readings = readings_store.query_readings(
            ReadingsQuery(
                sensor_id=sample_sensor.id,
                topic=Topics.GREEN_RATIO,
                since=test_reading.timestamp - 60,
            )
        )
        persisted_reading = next(
            reading
            for reading in persisted_readings
            if reading.correlation_id == "green-ratio-kafka-integration-test"
        )

        assert persisted_reading.topic == Topics.GREEN_RATIO
        assert persisted_reading.unit == "ratio"
        assert persisted_reading.sensor_id == sample_sensor.id
        assert persisted_reading.correlation_id == "green-ratio-kafka-integration-test"

    finally:
        bridge.disconnect()


def test_bridge_persists_camera_snapshot(
    kafka_bootstrap_servers: str,
    kafka_service: KafkaService,
    analytics_store: AnalyticsStore,
    readings_store,
    alert_store,
    controller_store,
    snapshot_store,
    sample_sensor,
) -> None:
    """Persist camera snapshots received from Kafka.

    Parameters
    ----------
    kafka_bootstrap_servers : str
        Kafka bootstrap servers for the test broker.
    kafka_service : KafkaService
        Producer service for publishing camera snapshots.
    readings_store, alert_store, controller_store, snapshot_store
        Dedicated stores used by the bridge.
    sample_sensor : dt.communication.dataclasses.SensorDescriptor
        Registered sensor descriptor.
    """
    test_config = type("TestConfig", (), {"KAFKA_URL": kafka_bootstrap_servers})
    bridge = setup_bridge(
        config=test_config,
        readings_storage=readings_store,
        alert_storage=alert_store,
        analytics_storage=analytics_store,
        controller_storage=controller_store,
        snapshot_storage=snapshot_store,
    )
    assert isinstance(bridge, KafkaService)

    try:
        wait_for_kafka_service_ready(
            bridge, expected_topics={Topics.CAMERA_IMAGE_TOP.raw, Topics.ALERTS}
        )

        snapshot = CameraSnapshot(
            plant_id=sample_sensor.plant_id,
            sensor_id=sample_sensor.id,
            timestamp=time.time(),
            topic=Topics.CAMERA_IMAGE_TOP,
            correlation_id="camera-kafka-integration-test",
            mime_type="image/jpeg",
            image="aGVsbG8=",
            width=640,
            height=480,
        )
        kafka_service.publish(Topics.CAMERA_IMAGE_TOP.raw, snapshot)

        def snapshot_persisted() -> bool:
            latest = snapshot_store.get_latest_camera_snapshot(plant_id=sample_sensor.plant_id)
            return latest is not None and latest.correlation_id == "camera-kafka-integration-test"

        wait_until(snapshot_persisted, timeout_seconds=10.0, interval_seconds=0.25)

    finally:
        bridge.disconnect()


def test_bridge_persists_sensor_alert_event(
    kafka_bootstrap_servers: str,
    kafka_service: KafkaService,
    analytics_store: AnalyticsStore,
    readings_store,
    alert_store,
    controller_store,
    snapshot_store,
    sample_sensor,
) -> None:
    """Persist sensor alert events received from Kafka.

    Parameters
    ----------
    kafka_bootstrap_servers : str
        Kafka bootstrap servers for the test broker.
    kafka_service : KafkaService
        Producer service for publishing alert events.
    readings_store, alert_store, controller_store, snapshot_store
        Dedicated stores used by the bridge.
    sample_sensor : dt.communication.dataclasses.SensorDescriptor
        Registered sensor descriptor.
    """
    alert_key = "high_temp:sensor_test"
    alert_store.save_alert_definition(
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
    bridge = setup_bridge(
        config=test_config,
        readings_storage=readings_store,
        alert_storage=alert_store,
        analytics_storage=analytics_store,
        controller_storage=controller_store,
        snapshot_storage=snapshot_store,
    )
    assert isinstance(bridge, KafkaService)

    try:
        wait_for_kafka_service_ready(bridge, {Topics.ALERTS})

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
            history = alert_store.get_alert_history(
                AlertHistoryQuery(plant_id=sample_sensor.plant_id, limit=20)
            )
            return any(event.correlation_id == "alert-integration-test-1" for event in history)

        wait_until(event_persisted, timeout_seconds=10.0, interval_seconds=0.25)

    finally:
        bridge.disconnect()


def test_bridge_persists_external_alert_event(
    kafka_bootstrap_servers: str,
    kafka_service: KafkaService,
    analytics_store: AnalyticsStore,
    readings_store,
    alert_store,
    controller_store,
    snapshot_store,
    sample_sensor,
) -> None:
    """Persist external alert events received from Kafka.

    Parameters
    ----------
    kafka_bootstrap_servers : str
        Kafka bootstrap servers for the test broker.
    kafka_service : KafkaService
        Producer service for publishing alert events.
    readings_store, alert_store, controller_store, snapshot_store
        Dedicated stores used by the bridge.
    sample_sensor : dt.communication.dataclasses.SensorDescriptor
        Registered sensor descriptor.
    """
    alert_key = "ai_anomaly:plant_test"
    alert_store.save_alert_definition(
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
    bridge = setup_bridge(
        config=test_config,
        readings_storage=readings_store,
        alert_storage=alert_store,
        analytics_storage=analytics_store,
        controller_storage=controller_store,
        snapshot_storage=snapshot_store,
    )
    assert isinstance(bridge, KafkaService)

    try:
        wait_for_kafka_service_ready(bridge, {Topics.ALERTS})

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
            history = alert_store.get_alert_history(
                AlertHistoryQuery(plant_id=sample_sensor.plant_id, limit=20)
            )
            return any(event.correlation_id == "alert-integration-test-2" for event in history)

        wait_until(event_persisted, timeout_seconds=10.0, interval_seconds=0.25)

    finally:
        bridge.disconnect()


def test_bridge_persists_action_status_events(
    kafka_bootstrap_servers: str,
    kafka_service: KafkaService,
    metadata_store,
    analytics_store: AnalyticsStore,
    readings_store,
    alert_store,
    controller_store,
    snapshot_store,
    sample_plant_id: int,
) -> None:
    """Persist action status events received from Kafka."""
    actuator_id = metadata_store.register_actuator(sample_plant_id, "water_pump", 17, 1)
    test_config = type("TestConfig", (), {"KAFKA_URL": kafka_bootstrap_servers})
    bridge = setup_bridge(
        config=test_config,
        readings_storage=readings_store,
        alert_storage=alert_store,
        analytics_storage=analytics_store,
        controller_storage=controller_store,
        snapshot_storage=snapshot_store,
    )
    assert isinstance(bridge, KafkaService)

    try:
        wait_for_kafka_service_ready(bridge, {Topics.ACTIONS})

        kafka_service.publish(
            Topics.ACTIONS,
            ActionCommand(
                plant_id=sample_plant_id,
                execution_id="manual:plant-test:pump:on:1",
                action_id="manual:plant-test:pump:on",
                actuator_id=actuator_id,
                event_at=time.time(),
                duration=0.0,
                command="ON",
                reason="bridge integration test",
                correlation_id="action-integration-test",
                source="manual",
                status="completed",
            ),
        )

        def action_persisted() -> bool:
            history = controller_store.get_action_history(
                ActionHistoryQuery(plant_id=sample_plant_id, limit=20)
            )
            return any(item.correlation_id == "action-integration-test" for item in history)

        wait_until(action_persisted, timeout_seconds=10.0, interval_seconds=0.25)

    finally:
        bridge.disconnect()


def test_bridge_persists_analytics_outputs(
    kafka_bootstrap_servers: str,
    kafka_service: KafkaService,
    analytics_store: AnalyticsStore,
    readings_store,
    alert_store,
    controller_store,
    snapshot_store,
    sample_sensor,
) -> None:
    """Persist analytics outputs received from Kafka."""
    test_config = type("TestConfig", (), {"KAFKA_URL": kafka_bootstrap_servers})
    bridge = setup_bridge(
        config=test_config,
        readings_storage=readings_store,
        alert_storage=alert_store,
        analytics_storage=analytics_store,
        controller_storage=controller_store,
        snapshot_storage=snapshot_store,
    )
    assert isinstance(bridge, KafkaService)

    try:
        wait_for_kafka_service_ready(
            bridge,
            {
                Topics.ANALYTICS_HEALTH,
                Topics.ANALYTICS_FORECAST,
                Topics.RECOMMENDATIONS_COMPLETED,
            },
        )

        health = HealthAssessment(
            plant_id=sample_sensor.plant_id,
            timestamp=time.time(),
            correlation_id="analytics-health-corr",
            state=HealthState.CRITICAL,
            score=0.14,
            summary="Plant is dry and stressed",
            confidence=0.92,
            model_metadata=ModelMetadata(model_name="health-baseline", model_version="1.0"),
        )
        forecast = ForecastResult(
            plant_id=sample_sensor.plant_id,
            timestamp=time.time(),
            correlation_id="analytics-forecast-corr",
            metric="soil_moisture",
            horizon_seconds=3600,
            predicted_value=24.0,
            unit="%",
            model_metadata=ModelMetadata(
                model_name="moisture-forecaster", model_version="2.0"
            ),
            features_used=["soil_moisture.last"],
            inference_metadata={"confidence": 0.81},
        )
        recommendation = Recommendation(
            plant_id=sample_sensor.plant_id,
            timestamp=time.time(),
            correlation_id="analytics-recommendation-corr",
            confidence=0.61,
            reason="Health is stressed but irrigation guard is not met",
            actions=[RecommendedAction(capability="advisory", command="inspect_plant")],
            model_metadata=ModelMetadata(model_name="policy-engine", model_version="1.0"),
            action_results=[ActionResult(action_index=0, status="advisory_only")],
        )

        kafka_service.publish(Topics.ANALYTICS_HEALTH, health)
        kafka_service.publish(Topics.ANALYTICS_FORECAST, forecast)
        kafka_service.publish(Topics.RECOMMENDATIONS_COMPLETED, recommendation)

        def health_persisted() -> bool:
            history = analytics_store.get_health_history(
                HealthHistoryQuery(
                    plant_id=sample_sensor.plant_id,
                    correlation_id="analytics-health-corr",
                )
            )
            return (
                len(history) == 1
                and history[0].correlation_id == health.correlation_id
                and history[0].state == health.state
                and history[0].summary == health.summary
            )

        def forecast_persisted() -> bool:
            history = analytics_store.get_forecast_history(
                ForecastHistoryQuery(
                    plant_id=sample_sensor.plant_id,
                    correlation_id="analytics-forecast-corr",
                    metric="soil_moisture",
                    horizon_seconds=3600,
                )
            )
            return (
                len(history) == 1
                and history[0].correlation_id == forecast.correlation_id
                and history[0].metric == forecast.metric
                and history[0].predicted_value == forecast.predicted_value
            )

        def recommendation_persisted() -> bool:
                history = analytics_store.get_recommendation_history(
                    RecommendationHistoryQuery(
                        plant_id=sample_sensor.plant_id,
                        correlation_id="analytics-recommendation-corr",
                    )
                )
                if len(history) != 1:
                    return False
                loaded = history[0]
                return (
                    loaded.plant_id == recommendation.plant_id
                    and loaded.correlation_id == recommendation.correlation_id
                    and loaded.timestamp == pytest.approx(recommendation.timestamp, abs=1e-6)
                    and loaded.reason == recommendation.reason
                    and loaded.confidence == recommendation.confidence
                    and loaded.actions == recommendation.actions
                    and loaded.action_results == recommendation.action_results
                )

        wait_until(health_persisted, timeout_seconds=10.0, interval_seconds=0.25)
        wait_until(forecast_persisted, timeout_seconds=10.0, interval_seconds=0.25)
        wait_until(recommendation_persisted, timeout_seconds=10.0, interval_seconds=0.25)

    finally:
        bridge.disconnect()
