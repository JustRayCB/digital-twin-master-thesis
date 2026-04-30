"""Alert DTOs aligned with the alternative alert schema.

This module defines the alert DTOs that align with the alternative schema:
- AlertStatus: lifecycle states
- AlertDefinition: invariant alert properties (composite key: alert_key + plant_id)
- AlertHistoryEvent and variants: append-only events with DB PK mapping
- SensorAlertEvent: history event with processed reading and thresholds
- ExternalAlertEvent: history event with metadata payload
"""

from dataclasses import dataclass, field
from enum import StrEnum

from dt.analytics.alerts.rules import SeverityLevel
from dt.communication.dataclasses.processed_sensor_data import ProcessedSensorData

from .alert_type import AlertType


class AlertStatus(StrEnum):
    """Alert lifecycle states."""

    ACTIVE = "active"
    IGNORED = "ignored"
    ACKNOWLEDGED = "acknowledged"
    CLEARED = "cleared"


@dataclass
class AlertDefinition:
    """Invariant alert properties stored in alert_definitions."""

    alert_key: str
    plant_id: int
    sensor_id: int | None
    source: str
    rule_id: str | None
    rule_name: str | None
    kind: AlertType
    persistence_count: int
    cooldown_seconds: int


@dataclass
class AlertHistoryEvent:
    """Append-only history event stored in alert_history."""

    alert_key: str
    plant_id: int
    timestamp: float
    status: AlertStatus
    severity: SeverityLevel
    message: str
    correlation_id: str
    acknowledged_by: str | None = None
    acknowledged_ts: float | None = None
    cleared_ts: float | None = None


@dataclass
class SensorAlertEvent(AlertHistoryEvent):
    """History event for sensor alerts with reading context."""

    reading: ProcessedSensorData = field(kw_only=True)
    threshold_op: str | None = field(default=None, kw_only=True)
    threshold_value: float | None = field(default=None, kw_only=True)
    range_min: float | None = field(default=None, kw_only=True)
    range_max: float | None = field(default=None, kw_only=True)


@dataclass
class ExternalAlertEvent(AlertHistoryEvent):
    """History event for external alerts with free-form metadata."""

    metadata: dict[str, str] = field(kw_only=True)
