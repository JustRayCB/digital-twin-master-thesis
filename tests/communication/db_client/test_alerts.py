"""Integration tests for alert-related database API client methods."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from dt.analytics.alerts.rules import SeverityLevel
from dt.communication.dataclasses import ProcessedSensorData, SensorDescriptor
from dt.communication.dataclasses.alerts.alert_record import (
    AlertDefinition,
    AlertHistoryEvent,
    AlertStatus,
    ExternalAlertEvent,
    SensorAlertEvent,
)
from dt.communication.dataclasses.alerts.alert_type import AlertType
from dt.communication.dataclasses.queries import ActiveAlertsQuery, AlertHistoryQuery
from dt.communication.db_client import DatabaseApiClient
from dt.communication.topics import Topics

pytestmark = [pytest.mark.requires_timescale]


def test_get_alert_history_parses_polymorphic_events(
    database_api_client: DatabaseApiClient,
    alert_store,
    sensor: SensorDescriptor,
) -> None:
    """Return sensor, external, and base alert history events from the real API."""
    definition = AlertDefinition(
        alert_key="rule1:temp",
        plant_id=sensor.plant_id,
        sensor_id=sensor.id,
        source="temperature",
        rule_id="rule1",
        rule_name="High temp",
        kind=AlertType.SENSOR,
        persistence_count=3,
        cooldown_seconds=300,
    )
    alert_store.save_alert_definition(definition)
    alert_store.save_alert_definition(
        AlertDefinition(
            alert_key="ai:anomaly",
            plant_id=sensor.plant_id,
            sensor_id=None,
            source="ai",
            rule_id=None,
            rule_name=None,
            kind=AlertType.EXTERNAL,
            persistence_count=1,
            cooldown_seconds=0,
        )
    )
    alert_store.save_alert_definition(
        AlertDefinition(
            alert_key="base:event",
            plant_id=sensor.plant_id,
            sensor_id=None,
            source="system",
            rule_id=None,
            rule_name=None,
            kind=AlertType.EXTERNAL,
            persistence_count=1,
            cooldown_seconds=0,
        )
    )

    alert_store.save_alert_event(
        SensorAlertEvent(
            alert_key="rule1:temp",
            plant_id=sensor.plant_id,
            timestamp=1_234_567_890.0,
            status=AlertStatus.ACTIVE,
            severity=SeverityLevel.WARNING,
            message="High temp",
            correlation_id="corr1",
            reading=ProcessedSensorData(
                plant_id=sensor.plant_id,
                sensor_id=sensor.id,
                timestamp=1_234_567_890.0,
                topic=Topics.TEMPERATURE,
                value=25.5,
                unit="C",
                correlation_id="corr1",
                flags={},
                dq_score=1.0,
                imputed=False,
            ),
        )
    )
    alert_store.save_alert_event(
        ExternalAlertEvent(
            alert_key="ai:anomaly",
            plant_id=sensor.plant_id,
            timestamp=1_234_567_891.0,
            status=AlertStatus.ACTIVE,
            severity=SeverityLevel.CRITICAL,
            message="Anomaly detected",
            correlation_id="corr2",
            metadata={"model": "demo"},
        )
    )
    alert_store.save_alert_event(
        AlertHistoryEvent(
            alert_key="base:event",
            plant_id=sensor.plant_id,
            timestamp=1_234_567_892.0,
            status=AlertStatus.ACKNOWLEDGED,
            severity=SeverityLevel.INFO,
            message="Acknowledged",
            correlation_id="corr3",
            acknowledged_by="ray",
            acknowledged_ts=1_234_567_892.5,
        )
    )

    events = database_api_client.get_alert_history(
        AlertHistoryQuery(plant_id=sensor.plant_id, limit=50)
    )

    assert len(events) == 3
    by_key = {event.alert_key: event for event in events}
    assert isinstance(by_key["rule1:temp"], SensorAlertEvent)
    assert by_key["rule1:temp"].severity is SeverityLevel.WARNING
    assert isinstance(by_key["ai:anomaly"], ExternalAlertEvent)
    assert by_key["ai:anomaly"].severity is SeverityLevel.CRITICAL
    assert isinstance(by_key["base:event"], AlertHistoryEvent)
    assert by_key["base:event"].status is AlertStatus.ACKNOWLEDGED


def test_get_active_alerts_returns_real_active_events(
    database_api_client: DatabaseApiClient,
    alert_store,
    sensor: SensorDescriptor,
) -> None:
    """Return active alerts and deserialize sensor payloads from the real API."""
    definition = AlertDefinition(
        alert_key="rule1:temp",
        plant_id=sensor.plant_id,
        sensor_id=sensor.id,
        source="temperature",
        rule_id="rule1",
        rule_name="High temp",
        kind=AlertType.SENSOR,
        persistence_count=3,
        cooldown_seconds=300,
    )
    alert_store.save_alert_definition(definition)
    alert_store.save_alert_definition(
        AlertDefinition(
            alert_key="ai:anomaly",
            plant_id=sensor.plant_id,
            sensor_id=None,
            source="ai",
            rule_id=None,
            rule_name=None,
            kind=AlertType.EXTERNAL,
            persistence_count=1,
            cooldown_seconds=0,
        )
    )
    alert_store.save_alert_event(
        SensorAlertEvent(
            alert_key="rule1:temp",
            plant_id=sensor.plant_id,
            timestamp=1_234_567_890.0,
            status=AlertStatus.ACTIVE,
            severity=SeverityLevel.WARNING,
            message="High temp",
            correlation_id="corr1",
            reading=ProcessedSensorData(
                plant_id=sensor.plant_id,
                sensor_id=sensor.id,
                timestamp=1_234_567_890.0,
                topic=Topics.TEMPERATURE,
                value=25.5,
                unit="C",
                correlation_id="corr1",
                flags={},
                dq_score=1.0,
                imputed=False,
            ),
        )
    )
    alert_store.save_alert_event(
        ExternalAlertEvent(
            alert_key="ai:anomaly",
            plant_id=sensor.plant_id,
            timestamp=1_234_567_891.0,
            status=AlertStatus.ACTIVE,
            severity=SeverityLevel.CRITICAL,
            message="Anomaly detected",
            correlation_id="corr2",
            metadata={"model": "demo"},
        )
    )

    alerts = database_api_client.get_active_alerts(ActiveAlertsQuery(plant_id=sensor.plant_id))

    assert len(alerts) == 2
    by_key = {alert.alert_key: alert for alert in alerts}
    assert isinstance(by_key["rule1:temp"], SensorAlertEvent)
    assert by_key["rule1:temp"].reading.topic is Topics.TEMPERATURE
    assert isinstance(by_key["ai:anomaly"], ExternalAlertEvent)
    assert by_key["ai:anomaly"].metadata["model"] == "demo"


def test_ensure_alert_definition_posts_to_real_api(
    database_api_client: DatabaseApiClient,
    alert_store,
    sensor: SensorDescriptor,
) -> None:
    """Persist alert definitions through the database API."""
    definition = AlertDefinition(
        alert_key="temp_high:sensor_1",
        plant_id=sensor.plant_id,
        sensor_id=sensor.id,
        source="temperature",
        rule_id="temp_high",
        rule_name="High Temperature",
        kind=AlertType.SENSOR,
        persistence_count=3,
        cooldown_seconds=300,
    )

    database_api_client.ensure_alert_definition(definition)

    with alert_store.engine.begin() as conn:
        stored = conn.execute(
            text(
                """
                SELECT alert_key, plant_id, sensor_id, source, rule_id, rule_name, kind,
                       persistence_count, cooldown_seconds
                FROM alert_definitions
                WHERE alert_key = :alert_key AND plant_id = :plant_id
                """
            ),
            {"alert_key": definition.alert_key, "plant_id": definition.plant_id},
        ).mappings().one()

    assert stored["alert_key"] == definition.alert_key
    assert stored["plant_id"] == definition.plant_id
    assert stored["sensor_id"] == definition.sensor_id
    assert stored["source"] == definition.source
    assert stored["rule_id"] == definition.rule_id
    assert stored["rule_name"] == definition.rule_name
    assert stored["kind"] == definition.kind.value
    assert stored["persistence_count"] == definition.persistence_count
    assert stored["cooldown_seconds"] == definition.cooldown_seconds


def test_get_alert_history_wraps_real_request_failures() -> None:
    """Raise RuntimeError when the database service cannot be reached."""
    client = DatabaseApiClient(base_url="http://127.0.0.1:9")

    with pytest.raises(RuntimeError, match="Failed to fetch alert history"):
        client.get_alert_history(AlertHistoryQuery(plant_id=1))


def test_ensure_alert_definition_wraps_real_request_failures(plant_id: int) -> None:
    """Raise RuntimeError when the alert-definition API cannot be reached."""
    client = DatabaseApiClient(base_url="http://127.0.0.1:9")
    definition = AlertDefinition(
        alert_key="temp_high:sensor_1",
        plant_id=plant_id,
        sensor_id=7,
        source="temperature",
        rule_id="temp_high",
        rule_name="High Temperature",
        kind=AlertType.SENSOR,
        persistence_count=3,
        cooldown_seconds=300,
    )

    with pytest.raises(RuntimeError, match="Failed to upsert alert definition"):
        client.ensure_alert_definition(definition)
